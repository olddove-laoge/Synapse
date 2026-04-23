# Synapse 文件结构与接口规范

## 1. 文档目标

本文档用于统一 Synapse 项目的工程结构和系统对接方式，明确：

- 仓库文件结构
- 各目录/文件职责
- 系统间接口契约
- 状态流转约束

本文档是实施级规范，默认面向 MVP 到 Beta 阶段。

---

## 2. 顶层目录规范

```text
Synapse/
├─ apps/
│  ├─ api/                           # FastAPI 后端（对外 API）
│  ├─ worker/                        # 异步任务 Worker（索引、抽取、同步）
│  └─ web/                           # 前端（图谱 + 对话 + 审核）
├─ packages/
│  ├─ domain/                        # 领域模型与状态机
│  ├─ contracts/                     # 接口契约（Pydantic/TypeScript Schema）
│  ├─ ingestion/                     # 文档解析与标准化（LlamaParse adapter）
│  ├─ extraction/                    # 文档/对话结构化抽取
│  ├─ retrieval/                     # HippoRAG 封装与检索服务
│  ├─ memory/                        # Mem0 封装与记忆策略
│  ├─ graph/                         # Neo4j 图谱读写与合并
│  ├─ sync/                          # Neo4j <-> HippoRAG 同步
│  └─ common/                        # 通用组件（日志、配置、异常、ID）
├─ infra/
│  ├─ docker/                        # Dockerfile 与本地依赖
│  ├─ k8s/                           # 部署清单
│  └─ scripts/                       # 迁移脚本、运维脚本
├─ tests/
│  ├─ contract/                      # 契约测试
│  ├─ integration/                   # 集成测试
│  └─ e2e/                           # 端到端流程测试
├─ docs/
│  ├─ api/                           # OpenAPI 导出与示例
│  ├─ adr/                           # 架构决策记录
│  └─ runbooks/                      # 故障与发布手册
└─ openspec/
   └─ plans/                         # 规划文档（本文件所在位置）
```

---

## 3. 各目录与关键文件作用

## 3.1 apps/api（对外 API 服务）

### 关键文件

- `apps/api/main.py`
  - API 入口，注册路由、中间件、健康检查。
- `apps/api/dependencies.py`
  - 依赖注入容器，装配 retrieval/memory/graph/extraction 服务。
- `apps/api/routes/chat.py`
  - 对话接口，支持普通问答与节点定向问答。
- `apps/api/routes/documents.py`
  - 文档上传、解析触发、解析结果查询。
- `apps/api/routes/graphs.py`
  - 图谱查询、焦点视图、候选提交与发布。
- `apps/api/routes/notes.py`
  - 节点笔记 CRUD。
- `apps/api/routes/memory.py`
  - 用户记忆查询与重建触发。

## 3.2 apps/worker（异步任务）

### 关键文件

- `apps/worker/main.py`
  - Worker 进程入口。
- `apps/worker/tasks/ingest_tasks.py`
  - 文档解析与标准化任务。
- `apps/worker/tasks/extract_tasks.py`
  - 节点关系抽取任务。
- `apps/worker/tasks/sync_tasks.py`
  - Neo4j 到 HippoRAG 同步任务。
- `apps/worker/tasks/memory_tasks.py`
  - Mem0 异步写入任务。

## 3.3 packages/contracts（接口契约）

### 关键文件

- `packages/contracts/common.py`
  - 通用类型：ID、分页、时间戳、错误结构。
- `packages/contracts/document.py`
  - `Document`, `ParsedSection`, `ParsedChunk`。
- `packages/contracts/graph.py`
  - `Node`, `Edge`, `CandidateNode`, `CandidateEdge`, `GraphDelta`。
- `packages/contracts/chat.py`
  - `ChatRequest`, `ChatResponse`, `Citation`, `ToolTrace`。
- `packages/contracts/memory.py`
  - `MemoryRecallRequest`, `MemoryWriteRequest`, `MemoryRecord`。
- `packages/contracts/retrieval.py`
  - `RetrievalRequest`, `EvidenceItem`, `RetrievalResult`。

契约层是跨模块唯一真源，禁止各服务自定义临时字段绕过契约。

## 3.4 packages/ingestion（LlamaParse 适配）

### 关键文件

- `packages/ingestion/parser_adapter.py`
  - 封装 LlamaParse SDK；统一输出标准结构。
- `packages/ingestion/chunk_normalizer.py`
  - chunk 切分与重排，保证长度和 metadata 一致。
- `packages/ingestion/source_store.py`
  - 原文与解析结果落库/对象存储。

## 3.5 packages/extraction（统一抽取层）

### 关键文件

- `packages/extraction/doc_extractor.py`
  - 从 ParsedChunk 抽取候选节点/关系/evidence。
- `packages/extraction/chat_extractor.py`
  - 从对话轮次抽取候选节点/关系/洞察。
- `packages/extraction/payload_builder.py`
  - 构建 `GraphDelta` 写回载荷。
- `packages/extraction/confidence_policy.py`
  - 置信度阈值与草稿入队规则。

## 3.6 packages/retrieval（HippoRAG 封装）

### 关键文件

- `packages/retrieval/service.py`
  - 对外统一检索服务接口。
- `packages/retrieval/hipporag_client.py`
  - HippoRAG 调用与错误映射。
- `packages/retrieval/index_updater.py`
  - 增量更新索引。
- `packages/retrieval/node_projection.py`
  - 节点中心检索数据准备。

## 3.7 packages/memory（Mem0 封装）

### 关键文件

- `packages/memory/service.py`
  - 记忆召回与写入统一入口。
- `packages/memory/mem0_client.py`
  - Mem0 SDK 适配层。
- `packages/memory/write_policy.py`
  - 仅写长期有效记忆的策略。
- `packages/memory/dedup.py`
  - 记忆去重和更新逻辑。

## 3.8 packages/graph（Neo4j 图服务）

### 关键文件

- `packages/graph/repository.py`
  - Neo4j 读写封装。
- `packages/graph/merge_service.py`
  - 节点别名合并、关系归并。
- `packages/graph/focus_query.py`
  - Focus View 子图查询。
- `packages/graph/candidate_service.py`
  - draft/reviewed/published 状态管理。

## 3.9 packages/sync（图同步）

### 关键文件

- `packages/sync/neo4j_to_hipporag.py`
  - 从已发布图谱导出计算投影并同步 HippoRAG。
- `packages/sync/checkpoint_store.py`
  - 同步断点与重放控制。
- `packages/sync/reconcile.py`
  - 同步一致性校验。

---

## 4. 领域对象与状态约束

## 4.1 核心对象

- `Document`
- `ParsedChunk`
- `Node`
- `Edge`
- `CandidateNode`
- `CandidateEdge`
- `Evidence`
- `GraphDelta`
- `MemoryRecord`

## 4.2 候选知识状态机

```text
draft -> reviewed -> published
   \-> rejected
reviewed -> merged
```

约束：
- 仅 `published` 对象可进入 Neo4j 主图谱和 HippoRAG 主索引。
- `draft` 仅用于候选区，不参与正式问答上下文。
- `merged` 必须记录 merge target 和变更来源。

---

## 5. 对外 API 接口规范

统一前缀：`/api/v1`

## 5.1 文档接口

### `POST /documents/upload`

作用：上传文档并创建 `Document` 记录。

请求：`multipart/form-data`
- file: binary
- workspace_id: string
- graph_id: string

响应：
```json
{
  "document_id": "doc_xxx",
  "status": "uploaded"
}
```

### `POST /documents/{document_id}/parse`

作用：触发 LlamaParse + 标准化任务。

响应：
```json
{
  "document_id": "doc_xxx",
  "job_id": "job_parse_xxx",
  "status": "queued"
}
```

### `GET /documents/{document_id}`

作用：查询文档处理状态。

---

## 5.2 对话接口

### `POST /chat`

作用：普通问答。

请求：
```json
{
  "workspace_id": "ws_xxx",
  "graph_id": "graph_xxx",
  "user_id": "user_xxx",
  "message": "解释一下Raft与Paxos区别",
  "use_web_search": false
}
```

响应：
```json
{
  "answer": "...",
  "citations": [{"chunk_id": "chunk_xxx", "score": 0.82}],
  "candidate_delta_id": "delta_xxx"
}
```

### `POST /chat/node`

作用：节点定向问答。

请求：
```json
{
  "workspace_id": "ws_xxx",
  "graph_id": "graph_xxx",
  "user_id": "user_xxx",
  "node_id": "node_xxx",
  "message": "这个概念和CAP是什么关系"
}
```

---

## 5.3 图谱接口

### `GET /graphs/{graph_id}/focus?node_id=...`

作用：获取焦点节点及一阶邻居。

### `POST /graphs/{graph_id}/nodes`

作用：手工创建节点。

### `POST /graphs/{graph_id}/edges`

作用：手工创建关系。

### `POST /graphs/{graph_id}/candidates/review`

作用：候选知识审核。

请求：
```json
{
  "candidate_ids": ["cand_1", "cand_2"],
  "action": "approve"
}
```

### `POST /graphs/{graph_id}/candidates/publish`

作用：发布已审核候选，触发 Neo4j 写入和 HippoRAG 同步。

---

## 5.4 笔记接口

### `GET /nodes/{node_id}/notes`
### `POST /nodes/{node_id}/notes`
### `PATCH /notes/{note_id}`

作用：节点笔记查询和编辑。

---

## 5.5 记忆接口

### `GET /users/{user_id}/memory`

作用：查询用户长期记忆摘要。

### `POST /users/{user_id}/memory/rebuild`

作用：触发记忆重建任务。

---

## 6. 内部服务接口规范

## 6.1 ParseAdapter 接口

文件：`packages/ingestion/parser_adapter.py`

```python
class ParseAdapter(Protocol):
    def parse_document(self, document_id: str, source_uri: str) -> ParsedDocument: ...
```

规则：
- 输入必须是 `document_id + source_uri`。
- 输出必须是标准 `ParsedDocument`，禁止透传第三方原始响应。

## 6.2 ExtractionService 接口

文件：`packages/extraction/service.py`

```python
class ExtractionService(Protocol):
    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> GraphDelta: ...
    def extract_from_chat(self, turns: list[ChatTurn]) -> GraphDelta: ...
```

规则：
- 必须返回 evidence 引用。
- 必须附带置信度和抽取来源（doc/chat/web）。

## 6.3 RetrievalService 接口

文件：`packages/retrieval/service.py`

```python
class RetrievalService(Protocol):
    def retrieve_for_query(self, req: RetrievalRequest) -> RetrievalResult: ...
    def retrieve_for_node(self, graph_id: str, node_id: str, query: str) -> RetrievalResult: ...
    def update_index(self, graph_id: str, delta: GraphDelta) -> None: ...
```

规则：
- 必须返回 chunk/node 证据和分数。
- `update_index` 仅接收 `published` 变更。

## 6.4 MemoryService 接口

文件：`packages/memory/service.py`

```python
class MemoryService(Protocol):
    def recall(self, req: MemoryRecallRequest) -> list[MemoryRecord]: ...
    def write(self, req: MemoryWriteRequest) -> None: ...
```

规则：
- `write` 必须经过 write policy。
- 禁止写入短期噪声内容和可直接从图谱推导的事实。

## 6.5 GraphService 接口

文件：`packages/graph/service.py`

```python
class GraphService(Protocol):
    def apply_delta(self, graph_id: str, delta: GraphDelta) -> ApplyResult: ...
    def focus_view(self, graph_id: str, node_id: str) -> FocusGraph: ...
    def review_candidates(self, graph_id: str, ids: list[str], action: str) -> ReviewResult: ...
```

规则：
- `apply_delta` 默认写 draft，不得直接 published。
- published 动作必须带审计信息（who/when/why）。

---

## 7. 错误码与幂等规范

## 7.1 错误码

- `INVALID_ARGUMENT`
- `NOT_FOUND`
- `CONFLICT`
- `FAILED_PRECONDITION`
- `UPSTREAM_TIMEOUT`
- `UPSTREAM_BAD_RESPONSE`
- `INTERNAL_ERROR`

## 7.2 幂等

以下写接口必须支持 `Idempotency-Key`：
- `/documents/upload`
- `/chat`
- `/graphs/{graph_id}/candidates/publish`
- `/nodes/{node_id}/notes`

相同 key + 相同 payload 必须返回同一语义结果。

---

## 8. 版本与兼容规范

- 对外 API 采用 `/api/v1` 版本前缀。
- 契约 schema 采用语义化版本：`major.minor.patch`。
- `major` 变更必须提供迁移脚本和兼容窗口。
- 内部服务接口调整必须同步更新 `packages/contracts` 和契约测试。

---

## 9. 最小交付清单（按开发优先级）

1. `packages/contracts/*` 完成并冻结 v1。
2. `packages/ingestion/parser_adapter.py` + `chunk_normalizer.py` 完成。
3. `packages/extraction/*` 返回 `GraphDelta` 完成。
4. `packages/graph/candidate_service.py` 状态机完成。
5. `packages/retrieval/service.py` + HippoRAG 适配完成。
6. `packages/sync/neo4j_to_hipporag.py` 增量同步完成。
7. `apps/api/routes/*` 完成对外接口。
8. `tests/contract/*` 覆盖核心契约。

---

## 10. 强约束（必须遵守）

- LlamaParse 只负责文档解析，不负责对话抽取。
- 文档抽取与对话抽取统一走 Extraction Layer。
- Neo4j 是业务主图谱，HippoRAG 是检索计算层。
- 所有新知识先进入候选层，不得绕过审核直接入主图谱。
- 所有检索答案必须返回 evidence 引用。
- 任何跨模块数据结构变更必须先改 contracts，再改实现。
