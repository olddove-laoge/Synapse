# [Deprecated] GraphRAG MVP 数据结构设计

> Status: Deprecated (archived)
> Replaced by:
> - `openspec/plans/SYNAPSE_PROJECT_BUILD_DOC.md`
> - `openspec/plans/SYNAPSE_FILE_STRUCTURE_AND_INTERFACE_SPEC.md`
> Notes: 保留仅用于历史参考，不再作为当前实施规范。


## 一、组织结构（Workspace → Graph）

### 1.1 Workspace（工作空间）

用户的工作空间，用于组织多个图。

```typescript
interface Workspace {
  id: string;                      // 唯一标识 UUID
  name: string;                   // 工作空间名称
  description?: string;           // 描述
  
  // 成员
  owner_id: string;               // 所有者用户ID
  members?: UserMember[];        // 协作者（可选）
  
  // 设置
  settings: {
    default_graph_id?: string;    // 默认图ID
    is_public: boolean;           // 是否公开
  };
  
  created_at: string;
  updated_at: string;
}

interface UserMember {
  user_id: string;
  role: "owner" | "editor" | "viewer";
  joined_at: string;
}
```

### 1.2 Graph（图）

工作空间下的一个图，用户的主要工作单元。

```typescript
interface Graph {
  id: string;                      // 唯一标识 UUID
  workspace_id: string;           // 所属工作空间ID
  name: string;                   // 图名称
  description?: string;          // 描述
  
  // 用户笔记列表（图级别）
  user_notes: UserNote[];
  
  // 统计
  stats: {
    entity_count: number;
    relationship_count: number;
    document_count: number;
  };
  
  // 设置
  settings: {
    is_template: boolean;          // 是否为模板
  };
  
  created_at: string;
  updated_at: string;
}

interface UserNote {
  id: string;                     // 笔记唯一ID
  title: string;                  // 笔记标题（可选）
  content: string;                // 笔记内容（支持 Markdown）
  format: "markdown" | "plain";
  created_at: string;
  updated_at: string;
  order: number;                 // 笔记排序
}
```

### 1.3 层级关系

```
Workspace (工作空间)
  │
  ├── Graph 1 (图)
  │     ├── 实体 A (实体笔记 x N)
  │     │     ├── 用户笔记 1
  │     │     └── 用户笔记 2
  │     ├── 实体 B (实体笔记 x N)
  │     ├── 关系 A→B (关系笔记 x N)
  │     └── 图级别笔记 x N
  │
  └── Graph 2 (图)
        └── ...
```

---

## 二、核心数据结构

### 1.1 TextChunk（文本分块）

文档分块是 GraphRAG 的基础单元。

```typescript
interface TextChunk {
  id: string;                    // 唯一标识 UUID
  document_id: string;           // 所属文档ID
  content: string;               // 文本内容 (max 600 tokens)
  token_count: number;           // token 数量
  start_position: number;        // 在文档中的起始位置
  end_position: number;          // 在文档中的结束位置
  overlap_count: number;        // 与下一块的 overlap token 数
  metadata: {
    source: string;              // 来源类型: pdf/article/chat
    created_at: string;          // 创建时间 ISO8601
  };
}
```

### 1.2 Entity（实体）

从 TextChunk 中提取的关键实体节点。

```typescript
interface Entity {
  id: string;                    // 唯一标识 UUID
  name: string;                  // 实体名称
  type: string;                  // 实体类型: person/organization/concept/location/event
  description: string;          // LLM 生成的描述
  chunk_ids: string[];           // 关联的 TextChunk ID 列表
  confidence: number;            // 置信度 0-1
  attributes?: Record<string, any>;  // 额外属性
  
  // 用户笔记列表（多条）
  user_notes: UserNote[];
  
  created_at: string;
  updated_at: string;
}

interface UserNote {
  id: string;                    // 笔记唯一ID
  title: string;                 // 笔记标题（可选）
  content: string;               // 笔记内容（支持 Markdown）
  format: "markdown" | "plain";
  created_at: string;
  updated_at: string;
  order: number;                // 笔记排序
}
```

### 1.3 Relationship（关系）

实体之间的关系边。

```typescript
interface Relationship {
  id: string;                    // 唯一标识 UUID
  source_entity_id: string;      // 源实体ID
  target_entity_id: string;     // 目标实体ID
  description: string;          // 关系描述 (LLM 生成)
  weight: number;               // 权重 (出现次数)
  chunk_ids: string[];          // 来源的 TextChunk ID
  confidence: number;           // 置信度 0-1
  
  // 用户笔记列表（多条）
  user_notes: UserNote[];
  
  created_at: string;
}
```

### 1.4 Claim（声明）

关于实体的具体事实陈述。

```typescript
interface Claim {
  id: string;                    // 唯一标识 UUID
  entity_id: string;             // 关联实体ID
  content: string;              // 事实陈述内容
  verified: boolean;            // 是否已验证
  source_chunk_id: string;       // 来源 TextChunk
  created_at: string;
}
```

---

## 二、知识图谱结构（关联到 Graph）

### 2.1 KnowledgeGraph（知识图谱）

图数据库中的知识图谱，关联到 Graph。

```typescript
interface KnowledgeGraph {
  id: string;
  graph_id: string;               // 关联的 Graph ID
  
  // 核心元素
  entities: Entity[];
  relationships: Relationship[];
  claims: Claim[];
  
  // 统计信息
  stats: {
    entity_count: number;
    relationship_count: number;
    claim_count: number;
    chunk_count: number;
  };
  
  metadata: {
    source_document_count: number;
    total_tokens: number;
    created_at: string;
    updated_at: string;
  };
}
```

---

## 三、社区结构

### 3.1 Community（社区）

使用 Leiden 算法检测到的实体社区。

```typescript
interface Community {
  id: string;
  level: number;                  // 社区层级 0-3 (C0-C3)
  parent_id?: string;             // 父级社区ID (C0 无父级)
  
  // 社区成员
  entity_ids: string[];          // 社区内的实体ID列表
  relationship_ids: string[];   // 社区内的关系ID列表
  
  // 社区度量
  metrics: {
    size: number;                 // 实体数量
    internal_edges: number;       // 内部边数
    modularity: number;           // 模块度
  };
  
  created_at: string;
}
```

### 3.2 CommunitySummary（社区摘要）

LLM 为每个社区生成的摘要报告，同时支持用户编辑。

```typescript
interface CommunitySummary {
  id: string;
  community_id: string;           // 关联社区ID
  level: number;                  // 所属层级
  
  // LLM 生成的摘要（可编辑）
  summary: string;                // LLM 生成的摘要文本
  summary_source: "llm" | "user"; // 摘要来源：LLM生成 / 用户编辑
  token_count: number;           // token 数量
  
  // 用户笔记列表（多条）
  user_notes: UserNote[];
  
  // 元素引用（用于追溯）
  element_references: {
    entity_count: number;
    relationship_count: number;
    claim_count: number;
  };
  
  // 质量指标
  quality: {
    completeness: number;        // 完整性评分 0-1
    generated_at: string;        // 生成时间
  };
  
  created_at: string;
}
```

### 3.3 社区层级关系

```
C0 (根级)
  ├── C1-A (高级社区)
  │     ├── C2-A1 (中级社区)
  │     │     ├── C3-A1a (叶子社区)
  │     │     └── C3-A1b
  │     └── C2-A2
  │           └── C3-A2a
  └── C1-B
        └── ...
```

---

## 四、查询相关结构

### 4.1 QueryRequest（查询请求）

```typescript
type QueryMode = "local" | "global";

interface QueryRequest {
  id: string;
  query: string;                  // 用户查询文本
  mode: QueryMode;                // 查询模式
  
  // 可选参数
  options?: {
    community_level?: number;     // 指定社区层级 (0-3)
    top_k_community?: number;    // Global Query 取前K个社区
    include_sources?: boolean;    // 是否返回引用的 chunk
    max_tokens?: number;          // 答案最大 token 数
  };
  
  metadata: {
    user_id?: string;
    timestamp: string;
  };
}
```

### 4.2 LocalContext（局部上下文）

Local Query 返回的子图上下文。

```typescript
interface LocalContext {
  // 焦点实体
  focus_entity: Entity;
  
  // 一阶邻居
  neighbors: {
    entities: Entity[];
    relationships: Relationship[];
  };
  
  // 二阶邻居（可选）
  second_hop?: {
    entities: Entity[];
    relationships: Relationship[];
  };
  
  // 引用的 TextChunk
  source_chunks: TextChunk[];
}
```

### 4.3 GlobalContext（全局上下文）

Global Query Map 阶段生成的局部答案。

```typescript
interface GlobalContext {
  // 社区摘要列表
  community_summaries: CommunitySummary[];
  
  // Map 阶段结果
  community_answers: CommunityAnswer[];
  
  // Reduce 阶段结果
  final_answer?: Answer;
}

interface CommunityAnswer {
  community_id: string;
  level: number;
  answer: string;
  relevance_score: number;        // 0-100 打分
  source_chunks: string[];        // 引用的 chunk
}
```

### 4.4 QueryResponse（查询响应）

```typescript
interface QueryResponse {
  id: string;
  query: string;
  mode: QueryMode;
  
  // 答案
  answer: string;
  
  // 上下文引用
  context: LocalContext | GlobalContext;
  
  // 统计
  stats: {
    tokens_used: number;
    communities_retrieved?: number;
    entities_retrieved?: number;
    latency_ms: number;
  };
  
  created_at: string;
}
```

---

## 五、存储结构设计

### 5.1 图数据库 Neo4j Schema

```cypher
// 实体节点
CREATE TABLE entities (
  id STRING PRIMARY KEY,
  name STRING NOT NULL,
  type STRING,
  description TEXT,
  confidence FLOAT,
  attributes JSON,
  created_at DATETIME,
  updated_at DATETIME
)

// 关系边
CREATE TABLE relationships (
  id STRING PRIMARY KEY,
  source_entity_id STRING,
  target_entity_id STRING,
  description TEXT,
  weight INT DEFAULT 1,
  confidence FLOAT,
  created_at DATETIME,
  FOREIGN KEY (source_entity_id) REFERENCES entities(id),
  FOREIGN KEY (target_entity_id) REFERENCES entities(id)
)

// 实体-Chunk 关联（多对多）
CREATE TABLE entity_chunks (
  entity_id STRING,
  chunk_id STRING,
  confidence FLOAT,
  PRIMARY KEY (entity_id, chunk_id)
)

// TextChunk 表
CREATE TABLE text_chunks (
  id STRING PRIMARY KEY,
  document_id STRING,
  content TEXT,
  token_count INT,
  start_position INT,
  end_position INT,
  created_at DATETIME
)

// 社区表
CREATE TABLE communities (
  id STRING PRIMARY KEY,
  level INT,                      -- 0-3 对应 C0-C3
  parent_id STRING,
  entity_ids JSON,                -- JSON 数组
  size INT,
  modularity FLOAT,
  created_at DATETIME,
  FOREIGN KEY (parent_id) REFERENCES communities(id)
)

// 社区摘要表
CREATE TABLE community_summaries (
  id STRING PRIMARY KEY,
  community_id STRING,
  level INT,
  summary TEXT,
  token_count INT,
  completeness FLOAT,
  created_at DATETIME,
  FOREIGN KEY (community_id) REFERENCES communities(id)
)
```

---

## 六、API 接口设计

### 6.1 索引 Pipeline API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/index/documents | 文档导入并构建图谱 |
| POST | /api/v1/index/chunks | Text Chunking |
| POST | /api/v1/index/entities | 实体/关系抽取 |
| POST | /api/v1/index/communities | 社区检测 |
| POST | /api/v1/index/summaries | 社区摘要生成 |
| GET | /api/v1/graph | 获取图谱概览 |

### 6.2 查询 API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/query | 执行查询（自动判断模式） |
| POST | /api/v1/query/local | 局部查询 |
| POST | /api/v1/query/global | 全局查询 |

### 6.3 社区 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/communities | 获取所有社区 |
| GET | /api/v1/communities/{id} | 获取社区详情 |
| GET | /api/v1/communities/{id}/summary | 获取社区摘要 |
| GET | /api/v1/communities/{id}/entities | 获取社区内实体 |

---

## 七、数据流程示例

### 7.1 索引流程

```
输入文档
    ↓
TextChunking → [TextChunk_1, TextChunk_2, ...]
    ↓
Entity Extraction → [Entity_A, Entity_B, ...]
    ↓
Relationship Extraction → [Entity_A → Entity_B, ...]
    ↓
Knowledge Graph 构建
    ↓
Community Detection (Leiden) → [Community_1, Community_2, ...]
    ↓
Community Summary → [Summary_1, Summary_2, ...]
    ↓
索引完成
```

### 7.2 查询流程

```
用户查询: "什么是 CAP 定理？"
    ↓
查询模式判断 → local (具体概念查询)
    ↓
定位 "CAP 定理" 实体
    ↓
检索一阶邻居: [一致性, 可用性, 分区容错性, ...]
    ↓
构建 Local Context
    ↓
LLM 生成答案
    ↓
返回 QueryResponse

---

用户查询: "分布式系统的主要主题是什么？"
    ↓
查询模式判断 → global (主题理解)
    ↓
选择社区层级 C1
    ↓
Map: 各 C1 社区并行生成答案 + 打分
    ↓
Reduce: 排序聚合
    ↓
LLM 生成全局答案
    ↓
返回 QueryResponse
```

---

## 八、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2024-03-30 | 初始版本 |

*基于 arXiv:2404.16130 GraphRAG 论文设计*
