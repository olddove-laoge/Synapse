## Why

当前方案已经明确产品价值与交互路径，但在工程落地层仍缺少明确的语言与服务边界定义，容易导致实现阶段技术选型摇摆、迭代效率下降。现在需要把“Go 后端控制面 + Python GraphRAG 智能面”的分工固化为规范，以保障 MVP 快速交付并兼顾后续可扩展性。

## What Changes

- 明确后端主服务语言采用 Go，负责 API、鉴权、任务编排、通知策略与端云同步治理。
- 明确 GraphRAG 与模型工程采用 Python，负责实体关系抽取、图推理、检索重排、摘要生成与评测流水线。
- 新增跨语言契约规范，统一 Go 与 Python 间请求协议、幂等键、错误码与降级语义。
- 新增模型优化策略约束：MVP 阶段优先做抽取质量、检索质量、上下文构造优化，不将训练或微调作为前置门槛。
- 新增分阶段演进路径：先双服务闭环，再治理稳定性，再评估端侧增强与性能收敛。

## Capabilities

### New Capabilities
- `go-backend-control-plane`: 定义 Go 服务在控制面中的职责边界与可靠性要求。
- `python-graphrag-intelligence-plane`: 定义 Python 服务在 GraphRAG 与模型工程中的能力要求。
- `cross-language-contract-governance`: 定义跨语言调用契约、错误治理与降级协同机制。
- `mvp-model-optimization-strategy`: 定义 MVP 模型优化优先级与训练策略约束。

### Modified Capabilities
- 无

## Impact

- 架构层：由单一技术模糊实现转为控制面与智能面分层架构。
- 实施层：任务可按 Go 团队与 Python 团队并行拆分，降低互相阻塞。
- 风险层：通过契约与降级规范降低跨语言系统故障传播风险。
- 交付层：提高竞赛 Demo 的稳定性与可解释性，增强答辩时技术路线清晰度。