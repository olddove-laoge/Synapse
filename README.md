# 递归学习 Agent (Recursive Scholar)

基于 HippoRAG + Neo4j + DeepSeek + 阿里云 Embedding 的递归学习系统。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        递归学习 Agent                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   DeepSeek  │  │  阿里云     │  │        Neo4j            │ │
│  │    (LLM)    │  │  Embedding  │  │      (图数据库)          │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
│         │                │                      │               │
│         ▼                ▼                      ▼               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    HippoRAG 核心                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │  OpenIE     │  │   PPR检索   │  │   图构建/查询    │  │  │
│  │  │ (三元组提取) │  │(个性化PageRank)│  │  (igraph→Neo4j) │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    递归学习逻辑                           │  │
│  │  - 知识缺口检测                                           │  │
│  │  - 前置概念追溯                                           │  │  │
│  │  - 认知状态追踪 (Mem0)                                     │  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 组件说明

| 组件 | 功能 | 配置 |
|------|------|------|
| **DeepSeek** | LLM，用于三元组提取和问答 | `DEEPSEEK_API_KEY` |
| **阿里云 DashScope** | Embedding 模型 | `DASHSCOPE_API_KEY` |
| **HippoRAG** | 知识图谱构建 + PPR 检索 | 本地存储 |
| **Neo4j** | 图数据库存储和可视化 | Neo4j Desktop |
| **LlamaParse** | PDF 解析（已完成） | `LLAMA_CLOUD_API_KEY` |

## 快速开始

### 1. 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# HippoRAG (本地安装)
cd HippoRAG
pip install -e .
cd ..
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写你的 API Key:

```bash
cp .env.example .env
```

编辑 `.env`:
```env
# DeepSeek API配置
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 阿里云 DashScope配置
DASHSCOPE_API_KEY=sk-your-key

# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### 3. 启动 Neo4j

1. 打开 Neo4j Desktop
2. 创建或启动一个数据库
3. 确认 bolt 端口在 7687

### 4. 运行文档导入

```bash
python ingest_to_neo4j.py
```

这会:
1. 读取 `parsed_paper.md` (已解析的 Transformer 论文)
2. 使用 DeepSeek 提取实体和关系
3. 构建知识图谱
4. 同步到 Neo4j
5. 测试检索功能

## 数据结构

### Neo4j 图模型

```cypher
// 实体节点
(:Entity {id: "...", content: "multi-head attention", source: "attention_paper"})

// 文档节点
(:Passage {id: "...", content: "...", preview: "...", source: "attention_paper"})

// 关系
(:Entity)-[:RELATES_TO {weight: 1.0}]->(:Passage)
(:Entity)-[:RELATES_TO {weight: 0.8}]->(:Entity)
```

### 查询示例

```cypher
// 查看所有实体
MATCH (e:Entity) RETURN e.content LIMIT 20

// 查看与某个实体相关的文档
MATCH (e:Entity {content: "attention"})-[:RELATES_TO]->(p:Passage)
RETURN p.preview

// 查看图的统计信息
MATCH (n) RETURN labels(n) as type, count(n) as count
```

## 双循环架构

### 1. 知识沉淀循环 (Ingestion Pipeline)

```
PDF → LlamaParse → Markdown → HippoRAG(OpenIE) → Neo4j
```

- **LlamaParse**: 高保真 PDF 解析
- **OpenIE**: 提取 (实体1, 关系, 实体2) 三元组
- **PPR**: Personalized PageRank 构建图索引

### 2. 认知迭代循环 (Learning Loop)

```
用户问题 → Mem0(认知状态) → HippoRAG(PPR检索) → 递归判定
                ↓
        知识缺口? → 是 → 向下钻取 → 更新 Mem0
                ↓
               否 → 直接回答 → 更新 Mem0
```

- **Mem0**: 存储用户认知状态（已掌握/未掌握概念）
- **递归判定**: 检测知识点依赖关系
- **向下钻取**: 自动解释前置概念

## 文件结构

```
.
├── config.py                  # 统一配置
├── ingest_to_neo4j.py         # 主导入脚本
├── parsed_paper.md            # 已解析的论文
├── test.py                    # LlamaParse 测试
├── requirements.txt           # 依赖
├── .env.example              # 环境变量模板
├── HippoRAG/                 # HippoRAG 源码
│   └── src/hipporag/
└── outputs/                  # 输出目录
    └── attention_paper/      # 论文索引数据
        ├── triples.json      # 提取的三元组
        └── graph.pickle      # igraph 图数据
```

## Synapse API 骨架（已创建）

当前仓库已新增 FastAPI 后端骨架，路径如下：

```text
apps/api/
packages/contracts/
packages/common/
packages/{ingestion, extraction, retrieval, memory, graph}/
```

默认模型配置：
- LLM: DeepSeek (`SYNAPSE_LLM_PROVIDER=deepseek`, `SYNAPSE_LLM_MODEL=deepseek-chat`)
- Embedding: 阿里云 DashScope (`SYNAPSE_EMBEDDING_PROVIDER=aliyun`, `SYNAPSE_EMBEDDING_MODEL=text-embedding-v3`)

启动：

```bash
uvicorn apps.api.main:app --reload --port 8000
```

接口文档：
- http://127.0.0.1:8000/docs

已提供 stub 路由：
- `/api/v1/documents/*`
- `/api/v1/chat*`
- `/api/v1/graphs/*`
- `/api/v1/nodes/*`
- `/api/v1/users/*/memory*`

## 下一步开发

1. **接入真实服务实现**: 将 `Stub*Service` 替换为 LlamaParse/HippoRAG/Mem0/Neo4j 实现
2. **契约测试**: 为 `packages/contracts` 和关键 API 路由补充 contract tests
3. **候选审核流**: 完成 draft/reviewed/published 状态机与审计
4. **索引同步**: 完成 Neo4j -> HippoRAG 增量同步

## 故障排除

### HippoRAG 导入错误
```bash
# 确保 HippoRAG 已安装
cd HippoRAG
pip install -e .
```

### Neo4j 连接失败
- 确认 Neo4j Desktop 已启动
- 检查 bolt 端口设置
- 验证用户名密码

### API 错误
- 确认 API Key 已设置
- 检查网络连接
- 查看 API 配额

## 参考

- [HippoRAG Paper](https://arxiv.org/abs/2405.14831)
- [HippoRAG GitHub](https://github.com/OSU-NLP-Group/HippoRAG)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [DeepSeek API](https://platform.deepseek.com/)
- [阿里云 DashScope](https://dashscope.aliyun.com/)
