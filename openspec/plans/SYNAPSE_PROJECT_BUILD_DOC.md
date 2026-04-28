# Synapse 项目建设文档

## 1. 项目定义

Synapse 是一个图式笔记 agent。它既能从用户上传的文档中抽取结构化知识，也能从持续对话中增量学习，把“文档理解 + 对话推理 + 记忆沉淀 + 图谱生长”合并成一个递归式学习系统。

目标形态不是传统聊天机器人，也不是静态知识图谱浏览器，而是一个会随着用户阅读、提问、整理、补充而不断长出新节点、新关系、新注释的知识工作台。

## 2. 目标与边界

### 2.1 核心目标

- 支持用户上传 PDF、DOCX、网页文本、长文章，并自动解析为结构化知识。
- 支持从零开始对话，在没有初始文档的情况下逐步生成知识图谱。
- 支持“针对某个节点发问”，让问答围绕局部子图展开。
- 支持模型在回答时同时使用 3 类上下文：
  - 用户已有图谱知识
  - 用户个体记忆
  - 外部网络搜索结果
- 支持把回答中新增的概念、关系、洞察回写到图谱，形成递归式学习闭环。
- 支持用户手工创建节点、关系，并在节点侧边栏维护自由文本笔记。

### 2.2 非目标

- 第一阶段不做多人协作编辑。
- 第一阶段不做全自动无审核入图，低置信度内容必须进入候选区。
- 第一阶段不追求大规模企业知识库治理能力。
- 第一阶段不追求超大图全景可视化，优先做 Focus View。

## 3. 实现难度评估

### 3.1 总体结论

这个项目的实现难度属于 **中高到高**，我建议按 **8/10** 看待。

它难的不是单点模型调用，而是四类系统在同一产品里要长期保持一致：

1. 文档解析结果要能稳定映射成图谱节点和关系。
2. 图谱检索结果要能真正提升问答，而不是只做展示层装饰。
3. 对话中新增知识要能增量入图，同时避免图谱污染和重复节点爆炸。
4. 用户显式笔记、系统自动抽取、模型短期记忆、长期知识记忆之间必须边界清晰。

### 3.2 难点拆解

| 模块 | 难度 | 难点 |
|------|------|------|
| LlamaParse 文档解析 | 中 | 文档格式差异大，表格、公式、页眉页脚清洗复杂 |
| HippoRAG 集成 | 中高 | 需要把它从“检索实验框架”包装成可增量、可服务化的核心检索层 |
| LlamaIndex agent 编排 | 中 | 工具路由不难，难在上下文组装、回写策略、工作流状态管理 |
| Mem0 记忆管理 | 中 | 关键不是接入，而是明确定义它记什么、不记什么 |
| 图谱增量写入 | 高 | 去重、别名归一、关系归并、人工确认流都很关键 |
| 前端图谱交互 | 中高 | 全景图不好用，必须做局部聚焦和渐进展开 |
| 递归学习闭环 | 高 | 需要保证“问答 -> 抽取 -> 审核 -> 入图 -> 再问答”闭环稳定 |

### 3.3 资源预估

**MVP 建议团队配置**：
- 后端/AI 工程 2 人
- 前端 1 人
- 产品/设计 0.5-1 人

**MVP 周期**：
- 快速 MVP：6-8 周
- 较稳 MVP：10-12 周
- 可上线 Beta：3-5 个月

## 4. 四个系统如何分工

四个系统不要平铺直连，而要明确职责边界。

### 4.1 LlamaParse：文档解析入口

LlamaParse 负责把原始文档转成适合后续处理的结构化内容。

它适合承担：
- PDF / DOCX / PPT / 网页正文解析
- 章节、标题、段落、表格、图片说明的结构恢复
- 输出 markdown、json、page-level metadata
- 为 chunking 和后续知识抽取提供更干净的输入

它不应该直接承担：
- 对话抽取
- 节点关系抽取
- 长期记忆管理
- 图谱推理
- 用户偏好记忆

### 4.1.1 Extraction Layer：统一知识抽取层

Extraction Layer 负责把文档文本或对话内容转换为候选知识结构。

它适合承担：
- 从文档 chunk 中抽取节点、关系、evidence
- 从对话轮次中抽取候选节点、候选关系、candidate insight
- 生成结构化 writeback payload，供候选图谱审核和发布
- 为图谱合并、去重、证据回溯提供统一格式

它不应该直接承担：
- 文档解析
- 用户长期记忆管理
- 图谱主存储
- Agent 路由

### 4.2 HippoRAG：核心 RAG / 图谱检索引擎

HippoRAG 负责 Synapse 的核心知识检索与联想式召回，是“知识记忆层”的核心。

它适合承担：
- 文档块索引
- 实体与关系增强的检索
- 多跳联想检索
- 节点相关上下文拼接
- 图谱问答时的 evidence retrieval

它不应该直接承担：
- Agent 路由与工具编排
- 用户个体偏好记忆
- UI 图谱编辑逻辑

### 4.3 LlamaIndex：可选 agent 编排层

LlamaIndex 的价值主要在“多工具工作流编排”，而不是替代当前已经成型的核心检索链。

它适合承担：
- 对话工作流编排
- tool calling
- 多步任务路由（如解析文档 -> 生成图谱 -> 问答）
- 路由策略（节点问答 / 全局问答 / 网络搜索 / 记忆召回）
- 响应后结构化抽取与回写流程触发

它不应该成为：
- 最终的事实存储层
- 唯一的记忆层
- 图数据库替代品
- HippoRAG 检索主链的替代品

当前项目阶段下，LlamaIndex 不是必须依赖，而更适合作为后续增强层：在现有能力已经闭环的基础上，提供自然语言驱动的多步工具编排。

### 4.4 Mem0：用户记忆层

Mem0 负责的是“关于用户”的记忆，不是“关于世界知识”的图谱本体。

它适合承担：
- 用户长期兴趣主题
- 用户最近在研究的问题
- 用户偏好的表达风格
- 用户对某些节点的关注轨迹
- 历史对话中值得长期保留的偏好或目标

它不应该承担：
- 文档事实主存储
- 节点关系主存储
- 图谱检索主引擎

### 4.5 一句话分工

- **LlamaParse**：把原始资料变成可处理内容
- **HippoRAG**：把内容变成可检索知识
- **LlamaIndex**：把能力组织成 agent 工作流
- **Mem0**：把用户行为和长期偏好沉淀成个体记忆

## 5. 推荐集成原则

### 5.1 先分清两类“记忆”

Synapse 至少有两套记忆系统，不能混：

1. **知识记忆**
   - 面向事实、概念、关系、来源
   - 载体：HippoRAG + 图数据库 + chunk/source store

2. **用户记忆**
   - 面向偏好、目标、近期任务、习惯
   - 载体：Mem0

结论：**HippoRAG 不替代 Mem0，Mem0 也不替代 HippoRAG。**

### 5.2 入图必须有“候选层”

所有来自对话或网络搜索的新知识，不要直接写入正式图谱，应该先进入 Candidate Graph。

建议分三层：
- Draft：模型抽取得到的候选节点/关系
- Reviewed：用户确认或规则通过
- Published：正式进入主图谱和 HippoRAG 索引

### 5.3 原始内容不可丢

必须保留：
- 原始文档
- 解析结果
- chunk
- 抽取证据 span
- 每条关系的来源

否则后续做纠错、节点合并、事实溯源会很痛苦。

### 5.4 Chunk 必须按文档结构切，而不是固定滑窗切

既然 PDF / DOCX 会统一经过 LlamaParse 格式化成结构化 markdown，那么 chunk 的最优策略应当是“标题到标题之间切一块”，而不是先把全文压平成连续字符串再固定长度滑窗。

推荐规则：
- `# / ## / ### ...` 之间的内容作为一个主块
- 标题本身不单独成 chunk，而是作为 chunk 的 `section_path`
- 过长块再在块内按句子二次切分
- 公式与其解释段尽量保持在同一 chunk
- 表格、图注、配置列表默认降权或不进入主抽取

推荐 chunk 结构：
- `chunk_id`
- `document_id`
- `section_path`（所有上级标题）
- `summary`（30 字以内概述）
- `content`
- `source_type`
- `metadata`

这样做的主要收益是：
- 降低重复节点和无意义节点
- 提高 fact 抽取质量
- 提升证据回填可解释性
- 让 chunk 更接近“学习卡片”的最小知识单元

### 5.4 UI 展示与检索结构解耦

前端展示的图，不应等于底层检索图的完整投影。

前端应主要展示：
- 焦点节点
- 一阶邻居
- 少量高价值二阶推荐
- 节点笔记和来源证据

## 6. 总体架构建议

## 6.1 MVP 架构建议

为了降低首发集成难度，**MVP 建议统一采用 Python 后端**，不要一开始就拆 Go 控制面。

原因很直接：
- HippoRAG、LlamaParse、LlamaIndex、Mem0 都是 Python 生态优先。
- 首版最大风险是智能链路跑不通，不是网关吞吐。
- 过早拆多语言会增加跨语言契约和联调成本。

### 6.2 推荐分层

```text
前端 Web / App
  ├─ 图谱 Focus View
  ├─ 对话面板
  ├─ 节点侧边栏笔记
  └─ 候选关系审核面板

API / Agent Service (FastAPI)
  ├─ Chat API
  ├─ Document API
  ├─ Graph API
  ├─ Node Note API
  └─ Memory API

Workflow Layer (LlamaIndex)
  ├─ Chat workflow
  ├─ Ingestion workflow
  ├─ Node-centric QA workflow
  ├─ Web-search workflow
  └─ Graph writeback workflow

Knowledge Layer
  ├─ LlamaParse
  ├─ HippoRAG
  ├─ Entity/Relation extractor
  ├─ Graph merge service
  └─ Re-ranker / summarizer

Memory Layer
  └─ Mem0

Storage Layer
  ├─ Postgres（业务主库）
  ├─ Neo4j（图谱存储）
  ├─ Object Storage（原文与解析结果）
  ├─ Redis（缓存/任务态）
  └─ Vector / HippoRAG persistence
```

### 6.3 为什么不建议 MVP 直接全堆到 LlamaIndex 里

LlamaIndex 很适合工作流编排，但不适合承担全部长期状态。

应该把它放在“编排层”，而不是“系统中枢数据库”。

## 7. 核心数据流设计

### 7.1 文档上传入图

```text
用户上传文档
  -> LlamaParse 解析
  -> 文档标准化（Document / Section / Chunk）
  -> Extraction Layer 抽取节点、关系、evidence
  -> 候选节点/关系生成
  -> 图合并与去重
  -> 写入 Neo4j
  -> 写入 HippoRAG 索引
  -> 前端展示图谱
```

### 7.2 从零开始对话入图

```text
用户发起对话
  -> LlamaIndex 选择工具
  -> 召回 Mem0 用户记忆
  -> 召回 HippoRAG 知识上下文
  -> 必要时触发网络搜索
  -> 生成回答
  -> Extraction Layer 对用户问题和模型回答做结构化抽取
  -> 形成候选节点/关系/洞察
  -> 用户确认后回写图谱
```

### 7.3 节点定向问答

```text
用户点击节点并提问
  -> 以 node_id 为中心构建局部子图
  -> HippoRAG 检索相关 chunk/evidence
  -> 结合节点笔记、邻居关系、来源文档
  -> 生成局部答案
  -> 输出可回写的新候选关系
```

### 7.4 节点笔记写入

```text
用户编辑节点侧边栏笔记
  -> 保存到 NodeNote
  -> 可选触发“从笔记提取结构化知识”
  -> 进入候选区
  -> 用户确认后入图
```

## 8. 四套系统的具体集成方式

## 8.1 LlamaParse -> Synapse Ingestion

输入：
- pdf
- docx
- markdown
- url 抓取文本

输出统一为：
- ParsedDocument
- ParsedSection
- ParsedChunk
- metadata（页码、标题路径、表格、图片说明）

建议内部标准结构：

```ts
interface ParsedChunk {
  id: string
  documentId: string
  sectionPath: string[]
  content: string
  pageStart?: number
  pageEnd?: number
  sourceType: "pdf" | "docx" | "web" | "chat"
  metadata: Record<string, any>
}
```

落地建议：
- 先统一成 markdown + chunk，不要让后续模块直接依赖 LlamaParse 原始响应格式。
- 加一层 parser adapter，避免未来替换解析器时全链路受影响。

## 8.2 ParsedChunk -> HippoRAG

HippoRAG 的接入建议不要裸接在 API 层，而是包一层 `KnowledgeRetrievalService`。

职责：
- 文档 chunks 索引
- 查询检索
- 节点中心检索
- 增量更新索引
- 返回 evidence ids 和分数

推荐包装接口：

```python
class KnowledgeRetrievalService:
    def index_chunks(self, chunks: list[ParsedChunk]) -> IndexResult: ...
    def retrieve_for_query(self, query: str, top_k: int) -> RetrievalResult: ...
    def retrieve_for_node(self, node_id: str, query: str) -> RetrievalResult: ...
    def update_graph_memory(self, additions: GraphDelta) -> None: ...
```

这样做的价值：
- 后面即使要替换成混合检索、加 reranker，Agent 层也不用改。
- HippoRAG 可以继续作为核心，但不会把业务层绑死在它的原始 API 设计上。

## 8.3 HippoRAG -> LlamaIndex

最合理的方式不是把 HippoRAG 当成黑盒 QA，而是把它包装成 LlamaIndex 可调用的检索工具。

建议提供 3 个工具：
- `graph_retrieve(query, scope)`
- `node_retrieve(node_id, query)`
- `graph_expand(seed_node_ids)`

LlamaIndex agent 在回答时可以按场景路由：
- 普通问题：graph_retrieve
- 节点点击后的追问：node_retrieve
- 递归式学习扩展：graph_expand + web_search

## 8.4 Mem0 -> LlamaIndex

Mem0 也应该被包装成工具，而不是直接混进 prompt。

建议最小工具集：
- `memory_recall(user_id, query)`
- `memory_write(user_id, memory_items)`
- `memory_related_topics(user_id)`

写入策略：
- 不要每轮对话都把整段内容写入 Mem0。
- 只写长期有效的信息，例如：
  - 用户最近在研究“分布式事务”
  - 用户偏好用例驱动的解释方式
  - 用户正在构建“数据库内核学习图谱”

## 8.5 Web Search -> 图谱扩展

Web search 不应该默认参与每次问答，而应作为扩展工具。

适合触发的场景：
- 当前图谱证据不足
- 用户明确问“最新”“近期”“外部资料”
- agent 判断需要补充背景知识

写回规则：
- 网络搜索得到的知识进入 Draft graph
- 标记 source_type = web
- 必须保留 URL、抓取时间、摘要证据
- 默认不直接覆盖已有高置信度关系

## 9. 推荐数据模型

Synapse 最少要有以下核心实体。

### 9.1 业务对象

- Workspace
- Graph
- Document
- ParsedChunk
- Node
- Edge
- NodeNote
- ConversationTurn
- CandidateNode
- CandidateEdge
- Evidence
- UserMemory

### 9.2 Node 类型建议

- Concept
- Person
- Organization
- Tool
- Framework
- Problem
- Question
- Insight
- Source
- Task

### 9.3 Edge 类型建议

- explains
- depends_on
- part_of
- related_to
- contrasts_with
- derived_from
- evidence_for
- question_about
- inspired_by
- implements

### 9.4 关键字段

`Node`
- id
- graph_id
- type
- title
- summary
- aliases[]
- source_count
- confidence
- created_by（system/user）
- created_at
- updated_at

`Edge`
- id
- graph_id
- source_node_id
- target_node_id
- relation_type
- description
- evidence_ids[]
- confidence
- status（draft/reviewed/published）

`NodeNote`
- id
- node_id
- content
- rich_text / markdown
- author_type
- created_at
- updated_at

## 10. 推荐后端模块划分

### 10.1 ingestion-service
- 调用 LlamaParse
- chunk 标准化
- 文档入库

### 10.2 extraction-service
- 实体/关系/洞察抽取
- 证据 span 对齐
- 候选图生成

### 10.3 graph-service
- 节点去重
- 别名归一
- 关系合并
- Neo4j 读写

### 10.4 retrieval-service
- HippoRAG 索引与查询
- 节点中心检索
- 多跳召回

### 10.5 agent-service
- LlamaIndex workflow
- 工具路由
- 回复生成
- 回写触发

### 10.6 memory-service
- Mem0 recall/write
- 用户画像与长期偏好管理

### 10.7 note-service
- 节点笔记 CRUD
- 笔记转候选知识

## 11. 前端能力设计

### 11.1 推荐前端交互

不要首发做全图自由拖拽，先做这四块：

1. **Focus Graph**
   - 当前节点
   - 一阶邻居
   - 高价值关系标签

2. **Chat Panel**
   - 普通问答
   - 节点上下文问答
   - 回答中高亮引用节点

3. **Node Sidebar**
   - 节点摘要
   - 来源证据
   - 用户笔记
   - 相关问题

4. **Review Queue**
   - 待确认节点
   - 待确认关系
   - 冲突关系提醒

### 11.2 为什么 Review Queue 很重要

没有审核面板，递归学习最后会变成递归污染。

用户需要能快速执行：
- 接受
- 拒绝
- 合并到已有节点
- 修改关系类型

## 12. 推荐 API 边界

### 12.1 文档
- `POST /documents/upload`
- `GET /documents/{id}`
- `POST /documents/{id}/parse`

### 12.2 图谱
- `GET /graphs/{id}`
- `GET /graphs/{id}/focus?nodeId=...`
- `POST /graphs/{id}/nodes`
- `POST /graphs/{id}/edges`
- `POST /graphs/{id}/candidates/commit`

### 12.3 对话
- `POST /chat`
- `POST /chat/node`
- `POST /chat/expand`

### 12.4 笔记
- `GET /nodes/{id}/notes`
- `POST /nodes/{id}/notes`
- `PATCH /notes/{id}`

### 12.5 记忆
- `GET /users/{id}/memory`
- `POST /users/{id}/memory/rebuild`

## 13. 开发路线图

### Phase 0：技术验证（1-2 周）

目标：确认四套系统能跑通最小闭环。

交付物：
- LlamaParse 成功解析 PDF
- HippoRAG 成功完成索引与问答
- LlamaIndex 成功调用至少两个工具
- Mem0 成功写入和召回用户记忆

### Phase 1：MVP 基线（3-4 周）

目标：完成“文档 -> 图谱 -> 节点问答 -> 候选回写”闭环。

交付物：
- 单文档上传
- 基础节点/关系抽取
- Focus Graph 前端
- 节点侧边栏笔记
- 节点定向问答
- Review Queue

### Phase 2：递归学习（2-3 周）

目标：完成“从聊天长出新枝桠”。

交付物：
- 回答后自动抽取候选节点/关系
- 用户确认后入图
- 图谱增量更新 HippoRAG 索引
- 节点扩展问答

### Phase 3：外部知识扩展（2 周）

目标：把网络搜索纳入递归式学习。

交付物：
- web search tool
- 外部资料证据保留
- web-based draft 节点标记

### Phase 4：稳定化（持续）

目标：解决图谱质量与性能问题。

交付物：
- 别名合并规则
- 冲突关系检测
- 缓存与异步任务队列
- 检索评测与人工抽样评估

## 14. 风险与应对

| 风险 | 说明 | 应对 |
|------|------|------|
| 图谱污染 | 对话和搜索结果会生成噪声节点 | 引入 draft/review/published 三层 |
| 节点爆炸 | 同义词、别名、细粒度概念反复创建 | 做 alias + merge 策略 |
| 检索收益不明显 | 图谱只是展示，没有提升回答 | 先做检索评测，再做 UI 扩展 |
| Mem0 与图谱职责混乱 | 用户记忆和事实记忆互相覆盖 | 明确双记忆边界 |
| LlamaParse 输出不稳定 | 文档格式复杂，清洗代价高 | 加 parser adapter 和 normalization |
| 前端交互过重 | 全图渲染体验差 | 坚持 Focus View |

## 15. 关键技术决策建议

### 15.1 MVP 用 Python 一体化后端

原因：四套核心系统都在 Python 生态里，首阶段先把智能链路打通，比提前做多语言治理更重要。

### 15.2 图数据库选 Neo4j

原因：
- 开发期生态成熟
- 可视化和调试方便
- 节点关系查询表达力强

### 15.3 不要让 Mem0 存事实主数据

Mem0 适合用户记忆，不适合代替图谱主存储。

### 15.4 不要跳过审核层

递归式学习如果没有审核层，随着使用时间增长，错误会累积得很快。

## 16. 当前优先事项

在现阶段，最该优先做的不是继续讨论单个库能否接入，而是把系统对接面固定下来。

建议按下面顺序推进：

1. 定义统一中间数据模型
- ParsedDocument
- ParsedChunk
- CandidateNode
- CandidateEdge
- Evidence
- GraphDelta
- UserMemoryRecord

2. 定义四组系统契约
- LlamaParse -> Ingestion / Parse Adapter
- Extraction Layer -> Graph Writeback
- HippoRAG -> Retrieval Service
- Mem0 -> Memory Service

3. 定义增量更新状态机
- draft
- reviewed
- published
- rejected
- merged

4. 明确 Neo4j 和 HippoRAG 的边界
- Neo4j 作为业务主图谱
- HippoRAG 作为检索和图算法计算层
- 两者通过同步层联动，不直接互相替代

5. 先实现最小闭环
- 单文档解析
- 基础节点关系抽取
- 候选区审核
- 发布到 Neo4j
- 同步到 HippoRAG
- 节点中心问答

只有这五件事落地，后续 LlamaIndex 工作流、Mem0 写入策略、网络搜索扩展才不会反复返工。

## 17. MVP 验收标准

满足下面条件，就可以认为 Synapse MVP 成立：

- 用户能上传一份文档并自动生成初始知识图谱。
- 用户能不上传文档，直接通过对话生成第一批节点。
- 用户能点击某个节点继续提问并拿到局部图谱增强答案。
- 回答中新增的概念和关系能以候选形式展示给用户确认。
- 用户能手工创建节点、关系并为节点添加文本笔记。
- 系统能区分知识图谱记忆与用户个体记忆。
- 外部网络搜索补充的内容能被标记来源并安全回写。

## 18. 最终建议

从工程可控性看，Synapse 最合理的首发架构是：

- **LlamaParse 负责入口解析**
- **HippoRAG 负责核心知识检索**
- **LlamaIndex 负责 agent 工作流编排**
- **Mem0 负责用户长期记忆**
- **Neo4j + Postgres 负责结构化落库**
- **前端只做局部聚焦图，不做全图编辑器**

这样分层后，四个系统是互补关系，不会互相抢职责。

从产品成败看，真正决定 Synapse 质量的不是“能不能接上四个库”，而是下面三件事有没有做好：

1. 候选知识审核流
2. 图谱增量更新质量
3. 节点中心问答体验

这三件事做稳了，Synapse 就会更像一个会成长的知识 agent，而不是一个把聊天记录画成图的 demo。
