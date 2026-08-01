# FSB 上游集成落地计划

## 上游状态总结

| 上游项目 | 状态 | 集成方式 |
|---------|------|---------|
| fusion-artifacts-engine | ✅ 已就绪 (port 8892) | HTTP REST POST /api/v1/external/create |
| fusion-agent-studio | ✅ 已就绪 (HTTP via fusion-mlx) | HTTP JSON-RPC (skill.execute, workflow.run/approve) |
| fusion-cowork | ✅ 已就绪 (port 9760) | HTTP JSON-RPC (desk.module.register, desk.notification.push) |
| fusion-gateway | ❌ 仅骨架 (mock) | POST /gateway/v1/connector/{key}/action/{action} 路由已存在但返回 mock |
| fusion-rag | ❌ 缺内联写入 API | issue #27 已提，等落地 |
| fusion-mlx | ❌ 缺 Non-Admin API | issue #302 已提，等落地 |

## 可落地的集成任务（4个已解锁上游）

### Task 1: Artifact 自动创建集成
**目标**: 工作流产出自动调用 artifacts-engine 创建 Artifact

- 新增 src/fsb/engine/artifact_client.py - HTTP 客户端调用 artifacts-engine
  - create_external_artifact(...) POST http://127.0.0.1:8892/api/v1/external/create
- 修改 src/fsb/engine/runner.py - _execute_node OUTPUT_NODE 分支
  - 工作流完成时自动调用 artifact_client 创建 Artifact
  - 从 NodeConfig.extra 获取 artifact 配置 (name, type, project_id)
- 修改 src/fsb/routes/integration.py - 替换 create-artifact stub 为真实调用
- 新增配置 src/fsb/config.py - 上游服务 URL 配置（从环境变量读取）

### Task 2: Skill 真实执行集成
**目标**: Skill 节点执行时调用 fusion-mlx LLM API

- 新增 src/fsb/engine/llm_client.py - HTTP 客户端调用 fusion-mlx
  - chat_completion(model, messages, tools) POST http://localhost:11434/v1/chat/completions
  - Skill 类型为 PROMPT 时构造 prompt 调用 LLM 解析结果
- 修改 src/fsb/engine/runner.py - _execute_skill 方法
  - 替换 stub 为真实 LLM 调用
  - LLM 不可用时 fallback 到 stub 模式

### Task 3: Connector 真实调用集成
**目标**: Connector 节点执行时调用 fusion-gateway Action API

- 新增 src/fsb/engine/gateway_client.py - HTTP 客户端调用 fusion-gateway
  - execute_action(connector_key, action_key, params, connection_id)
  - list_connectors(), create_connection()
- 修改 src/fsb/engine/runner.py - _execute_connector 方法
  - 替换 stub 为 gateway_client 调用
  - gateway 不可用时 fallback 到 stub 模式

### Task 4: Cowork 侧边栏注册 + 审批通知集成
**目标**: FSB 启动时注册侧边栏模块；审批暂停时推送通知到 cowork

- 新增 src/fsb/engine/cowork_client.py - HTTP 客户端调用 fusion-cowork
  - register_module() JSON-RPC desk.module.register
  - push_notification() JSON-RPC desk.notification.push
- 修改 src/fsb/engine/runner.py - APPROVAL_GATE_NODE 分支
  - 暂停后调用 cowork_client.push_notification 推送审批通知
- 修改 src/fsb/app.py - 启动时注册 FSB 侧边栏模块

### Task 5: 统一配置 + 环境变量
**目标**: 所有上游 URL 从配置读取不硬编码

- 新增 src/fsb/config.py - 集中管理上游服务 URL
  - ARTIFACTS_ENGINE_URL default http://127.0.0.1:8892
  - FUSION_MLX_URL default http://localhost:11434
  - FUSION_GATEWAY_URL default http://localhost:8080
  - FUSION_COWORK_URL default http://localhost:9760
  - 所有值从环境变量 FSB_* 覆盖

### Task 6: 测试 + README 更新
- 新增 tests/test_integration.py - 集成客户端单元测试（mock HTTP）
- 更新 README.md - 新增集成配置说明

## 文件变更汇总

| 操作 | 文件 |
|------|------|
| 新增 | src/fsb/config.py |
| 新增 | src/fsb/engine/artifact_client.py |
| 新增 | src/fsb/engine/llm_client.py |
| 新增 | src/fsb/engine/gateway_client.py |
| 新增 | src/fsb/engine/cowork_client.py |
| 修改 | src/fsb/engine/runner.py |
| 修改 | src/fsb/routes/integration.py |
| 修改 | src/fsb/app.py |
| 新增 | tests/test_integration.py |
| 修改 | README.md |
