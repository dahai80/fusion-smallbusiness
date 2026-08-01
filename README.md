# Fusion Small Business

面向小微企业主/小团队的跨 SaaS 智能业务工作台。

## 产品定位

Fusion Small Business（FSB）是 Fusion Team/Enterprise 订阅内一键启用的业务能力模块，提供：
- 可视化拖拽 Workflow Canvas 搭建业务工作流
- 第三方 SaaS 连接器 + 本地文件双数据源
- 人工审批闸确保安全
- 工作流产出自动归档 Fusion Project 知识库

## 架构概览

```
Connectors（数据接入）→ Skills（原子能力）→ Workflows（业务流水线）
```

三层架构 + LangGraph 风格 DAG 工作流引擎，7 种节点类型：
- `START_NODE` / `END_NODE` — 流程边界
- `CONNECTOR_NODE` — SaaS 连接器调用
- `SKILL_NODE` — LLM/函数技能
- `CONDITION_NODE` — 条件分支
- `APPROVAL_GATE_NODE` — 人工审批闸（写操作必经）
- `OUTPUT_NODE` — 产出输出

## 项目结构

```
src/fsb/
├── __init__.py              # 包入口
├── app.py                   # FastAPI 应用 + 生命周期
├── models/
│   ├── common.py            # 枚举、工具函数、共享模型
│   ├── workspace.py         # Workspace 模型
│   ├── connector.py         # Connector 模型
│   ├── skill.py             # Skill 模型
│   ├── workflow.py          # Workflow + GraphDefinition 模型
│   ├── execution.py         # RunInstance + PendingTask 模型
│   ├── event.py             # EventTrigger + EventSubscription 模型
│   └── webhook.py           # Webhook 模型
├── db/
│   └── store.py             # SQLite 异步存储层（10 表）
├── config.py                # 集中式上游服务 URL 配置
├── engine/
│   ├── runner.py            # 工作流 DAG 执行引擎（含审批闸 + webhook 回调 + 上游集成）
│   ├── router.py            # 意图路由（slash 命令 + 自然语言模糊匹配）
│   ├── scheduler.py         # APScheduler cron 定时调度
│   ├── event_bus.py         # 事件驱动触发引擎
│   ├── webhook_dispatcher.py # Webhook HTTP 回调分发
│   ├── artifact_client.py   # fusion-artifacts-engine HTTP/JSON-RPC 客户端（创建/导出/移动KB/列表）
│   ├── llm_client.py        # fusion-mlx LLM API 客户端
│   ├── gateway_client.py    # fusion-gateway 连接器 HTTP 客户端（含 Connection CRUD + OAuth2 流程）
│   ├── cowork_client.py     # fusion-cowork JSON-RPC 2.0 客户端（含项目知识库同步/快照/导出）
│   └── rag_client.py        # fusion-rag 知识库/检索/问答 HTTP 客户端
├── routes/
│   ├── workspace.py         # Workspace CRUD + 导入导出
│   ├── connector.py         # Connector 连接/断开/刷新 + 元数据
│   ├── skill.py             # Skill CRUD + 测试
│   ├── workflow.py          # Workflow CRUD + 运行 + 调度
│   ├── execution.py         # 执行历史 + 审批操作
│   ├── integration.py       # 集成路由（canvas/project/artifact）
│   ├── external.py          # 外部触发 + 事件 + Webhook
│   └── variable.py          # 变量 + 模板
├── skills/
│   └── registry.py          # 15 个内置 Skill 定义
└── workflows/
    └── registry.py          # 15 个内置 Workflow 定义

tests/
├── conftest.py              # pytest fixtures
├── test_api.py              # API 集成测试
├── test_engine.py           # 引擎 + DAG 验证测试
├── test_event.py            # 事件触发 + 订阅测试
├── test_webhook.py          # Webhook CRUD 测试
└── test_integration.py      # 上游集成客户端 mock 测试
```

## API 端点

所有端点前缀：`/api/v1/fsb`

| 模块 | 端点 | 方法 |
|------|------|------|
| Health | `/health` | GET |
| Workspace | `/workspace` | POST/GET |
| Workspace | `/workspace/{wsId}` | GET/PUT/DELETE |
| Workspace | `/workspace/{wsId}/duplicate` | POST |
| Workspace | `/workspace/{wsId}/export` | POST |
| Workspace | `/workspace/import` | POST |
| Connector | `/workspace/{wsId}/connector` | POST/GET |
| Connector | `/workspace/{wsId}/connector/{connId}` | PUT/DELETE |
| Connector | `/workspace/{wsId}/connector/{connId}/refresh` | POST |
| Connector | `/workspace/{wsId}/connector/{connId}/disconnect` | POST |
| OAuth2 | `/workspace/{wsId}/connector/{connId}/oauth2/authorize` | POST |
| OAuth2 | `/workspace/{wsId}/connector/{connId}/oauth2/callback` | GET |
| Cowork | `/workspace/{wsId}/sync-knowledge` | POST |
| Cowork | `/workspace/{wsId}/import-snapshot` | POST |
| Cowork | `/workspace/{wsId}/export-to-project` | POST |
| Connector Meta | `/connector-meta` | GET |
| Connector Meta | `/connector-meta/{connectorKey}` | GET |
| Skill | `/workspace/{wsId}/skill` | POST/GET |
| Skill | `/workspace/{wsId}/skill/{skillId}` | GET/PUT/DELETE |
| Skill | `/workspace/{wsId}/skill/{skillId}/test` | POST |
| Workflow | `/workspace/{wsId}/workflow` | POST/GET |
| Workflow | `/workspace/{wsId}/workflow/{wfId}` | GET/PUT/DELETE |
| Workflow | `/workspace/{wsId}/workflow/{wfId}/run` | POST |
| Workflow | `/workspace/{wsId}/workflow/{wfId}/schedule` | POST/DELETE |
| Workflow | `/workspace/{wsId}/workflow/{wfId}/export` | POST |
| Execution | `/workspace/{wsId}/task/pending` | GET |
| Execution | `/workspace/{wsId}/task/{taskId}/approve` | POST |
| Execution | `/workspace/{wsId}/task/{taskId}/deny` | POST |
| Execution | `/workspace/{wsId}/task/{taskId}/edit` | POST |
| Execution | `/workspace/{wsId}/execution/history` | GET |
| Execution | `/workspace/{wsId}/execution/{runId}` | GET |
| Execution | `/workspace/{wsId}/execution/export` | GET |
| External | `/external/workflow/{wfId}/trigger` | POST |
| External | `/external/workflow/{wfId}/status` | GET |
| External | `/external/event` | POST |
| External | `/external/event/subscription` | POST/GET |
| External | `/external/event/subscription/{subId}` | DELETE |
| External | `/external/webhook/register` | POST |
| External | `/external/webhook` | GET |
| External | `/external/webhook/{webhookId}` | DELETE |
| Variable | `/workspace/{wsId}/variable` | GET/PUT |
| Template | `/workspace/{wsId}/template` | GET/POST |

## 快速启动

```bash
cd /Users/dahai/fusion/fusion-smallbusiness
source .venv/bin/activate

# 启动服务
uvicorn fsb.app:app --host 0.0.0.0 --port 8000

# 运行测试
pytest tests/ -v
```

## 内置 Skill（15 个）

| Skill | 说明 |
|-------|------|
| cash-flow-snapshot | 现金流快照 |
| draft-invoice-reminder | 催收邮件生成 |
| score-lead | 线索评分 |
| weekly-sales-report | 周销售报告 |
| expense-categorize | 支出分类 |
| customer-sentiment | 客户情绪分析 |
| contract-summary | 合同要点提取 |
| tax-reminder | 税务提醒 |
| email-draft | 邮件起草 |
| inventory-alert | 库存预警 |
| payroll-summary | 薪资摘要 |
| competitor-brief | 竞品简报 |
| slack-digest | Slack 摘要 |
| invoice-validate | 发票校验 |
| kpi-dashboard-data | KPI 仪表盘数据 |

## 内置 Workflow（15 个）

| Workflow | Slash 命令 | 说明 |
|----------|-----------|------|
| invoice-chase | `/invoice-chase` | 逾期发票催收 |
| lead-nurture | `/lead-nurture` | 线索培育跟进 |
| cash-flow-alert | `/cash-flow-alert` | 现金流预警（周 cron） |
| weekly-sales | `/weekly-sales` | 周销售报告 |
| expense-review | `/expense-review` | 支出审查 |
| customer-health | `/customer-health` | 客户健康度检查 |
| contract-review | `/contract-review` | 合同审查 |
| tax-filing-reminder | `/tax-reminder` | 税务申报提醒（月 cron） |
| inventory-check | `/inventory-check` | 库存盘点预警（工作日 cron） |
| payroll-process | `/payroll` | 薪资处理（月 cron） |
| slack-daily-digest | `/slack-digest` | Slack 每日摘要（工作日 cron） |
| invoice-validation | `/invoice-validate` | 发票合规校验 |
| kpi-dashboard | `/kpi` | KPI 仪表盘更新（工作日 cron） |
| competitor-watch | `/competitor-watch` | 竞品监控（周 cron） |
| multi-channel-outreach | `/outreach` | 多渠道触达 |

## 上游依赖 Issue 清单

FSB 依赖以下上游模块提供基础能力，已提交 issue 跟踪：

| 上游模块 | Issue | 诉求 | 状态 |
|----------|-------|------|------|
| fusion-gateway | [#2](https://github.com/dahai80/fusion-gateway/issues/2) | Connector 插件框架、OAuth2 代持、Action 统一调用接口、审计日志 | ✅ 已集成 |
| fusion-gateway | [#6](https://github.com/dahai80/fusion-gateway/issues/6) | OAuth2 授权委托流 + 凭据持久化 + 真实 SaaS API 调用 | ✅ 已集成 |
| fusion-gateway | [#7](https://github.com/dahai80/fusion-gateway/issues/7) | OAuth2 Provider + Token Refresh + AES 加密 | ✅ 已集成 |
| fusion-gateway | [#8](https://github.com/dahai80/fusion-gateway/issues/8) | HTTPS 终止 + AES 静态加密 | ✅ 已集成 |
| fusion-cowork | [#7](https://github.com/dahai80/fusion-cowork/issues/7) | desk.project.syncKnowledge — 接收项目知识库同步 | ✅ 已集成 |
| fusion-cowork | [#8](https://github.com/dahai80/fusion-cowork/issues/8) | desk.project.importSnapshot — 接收会话快照导入 | ✅ 已集成 |
| fusion-cowork | [#9](https://github.com/dahai80/fusion-cowork/issues/9) | desk.project.exportToProject — 导出空间内容到项目 | ✅ 已集成 |
| fusion-agent-studio | [#35](https://github.com/dahai80/fusion-agent-studio/issues/35) | LangGraph 工作流执行引擎、审批闸断点、上下文沙箱、Skill 注册/执行 | ✅ 已集成 |
| fusion-cowork | [#4](https://github.com/dahai80/fusion-cowork/issues/4) | 侧边栏入口、工作台会话隔离、权限模型复用、审批通知推送 | ✅ 已集成 |
| fusion-studio | [#28](https://github.com/dahai80/fusion-studio/issues/28) | 前端路由/页面注册、Canvas 组件复用、Workflow Canvas 集成 | ✅ 已集成（Plugin） |
| fusion-artifacts-engine | [#18](https://github.com/dahai80/fusion-artifacts-engine/issues/18) | 工作流产出 → Artifact 创建 API、Artifact 反向输入工作流 | ✅ 已集成 |
| fusion-rag | [#27](https://github.com/dahai80/fusion-rag/issues/27) | 产出物自动归档 Project 知识库、RAG 检索供工作流上下文加载 | ✅ 已集成 |
| fusion-mlx | [#302](https://github.com/dahai80/fusion-mlx/issues/302) | 非 Admin 模型管理 API、模型能力标签、Embedding 模型独立配置 | ✅ 已集成 |

## 上游集成配置

FSB 通过 HTTP/JSON-RPC 客户端与上游服务通信，所有 URL 通过环境变量配置：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `FSB_ARTIFACTS_ENGINE_URL` | `http://127.0.0.1:8892` | fusion-artifacts-engine 服务地址 |
| `FSB_FUSION_MLX_URL` | `http://localhost:11434` | fusion-mlx LLM API 地址 |
| `FSB_FUSION_GATEWAY_URL` | `http://localhost:8080` | fusion-gateway 服务地址 |
| `FSB_FUSION_COWORK_URL` | `http://localhost:9760` | fusion-cowork RPC 地址 |
| `FSB_FUSION_RAG_URL` | `http://127.0.0.1:11436` | fusion-rag 知识库服务地址 |
| `FSB_FUSION_RAG_API_KEY` | _(空)_ | fusion-rag API Key（可选） |
| `FSB_LLM_DEFAULT_MODEL` | `default` | 默认 LLM 模型名 |
| `FSB_EMBEDDING_MODEL` | `BGE-M3` | 默认 Embedding 模型名 |
| `FSB_HTTP_TIMEOUT` | `10` | HTTP 请求超时（秒） |
| `FSB_STANDALONE_MODE` | `true` | 独立模式：true 时集成路由返回 stub 响应，避免上游不可用时报错 |

集成点说明：
- **OUTPUT_NODE** → `artifact_client` + `rag_client`：工作流产出自动创建 Artifact 并归档到知识库
- **SKILL_NODE** → `llm_client`：Skill 节点调用 LLM 执行，支持模型列表查询和 Embedding
- **CONNECTOR_NODE** → `gateway_client`：SaaS 连接器 Action 调用，支持 Connection 全生命周期管理 + OAuth2 授权流
- **APPROVAL_GATE_NODE** → `cowork_client`：审批闸通知推送到工作台 + 项目知识库同步/快照导入/空间导出

所有客户端在连接失败时优雅降级，不会阻塞工作流执行。

## fusion-studio 插件

FSB 通过 fusion-studio 的 Plugin 机制提供前端集成，插件位于：

```
~/.fusion-studio/plugins/fsb.fusion/
├── manifest.json    # 插件元信息
└── main.py          # 入口（on_load/on_render_panel）
```

插件提供三个面板：
- **Dashboard** — 工作区概览、健康状态、快捷操作
- **Run Workflow** — 工作流列表和一键触发
- **Pending Approvals** — 待审批任务列表和 Approve/Deny 操作

## 设计文档

- [PRD 与方案文档](../architecture/fusion-smallbusiness-prd-plan.md)

## 环境设置

```bash
cd /Users/dahai/fusion/fusion-smallbusiness
source .venv/bin/activate
```
