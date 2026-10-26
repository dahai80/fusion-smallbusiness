# Fusion Small Business

[English](README.md)

> **版本 0.2.0** — 企业级发布。单节点 + 多节点（Postgres）生产就绪。见 [更新日志](#更新日志)。

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
├── seed.py                  # 启动时内置 Skill/Workflow 播种
├── auth.py                  # fusion-identity JWT 校验
├── tenant_dep.py            # 租户归属校验 + 管理员角色守卫
├── engine/
│   ├── runner.py            # 工作流 DAG 执行引擎（含审批闸 + webhook 回调 + 上游集成 + chat 通知）
│   ├── router.py            # 意图路由（slash 命令 + 自然语言模糊匹配）
│   ├── expr.py              # 基于 AST 的安全条件表达式求值
│   ├── chat_client.py       # fusion-chat HTTP 客户端（Agent 绑定/解绑 + 运行完成通知，fail-soft）
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
│   ├── workflow.py          # Workflow CRUD + 运行 + 调度 + Canvas 布局
│   ├── execution.py         # 执行历史 + 审批操作 + CSV 导出
│   ├── intent.py            # 意图匹配 / 命令列表 / 运行 路由
│   ├── integration.py       # 集成路由（canvas/project/artifact）
│   ├── external.py          # 外部触发 + 事件 + Webhook（租户守卫）
│   ├── chat.py              # Agent 绑定/解绑 + Chat 驱动工作流运行
│   └── variable.py          # 变量 + 模板
├── skills/
│   └── registry.py          # 15 个内置 Skill 定义
└── workflows/
    └── registry.py          # 15 个内置 Workflow 定义

tests/
├── conftest.py              # pytest fixtures
├── test_api.py              # API 集成测试
├── test_api_extended.py     # 扩展 API 端点测试（404/502/审批/集成/外部路由）
├── test_engine.py           # 引擎 + DAG 验证测试
├── test_event.py            # 事件触发 + 订阅测试
├── test_webhook.py          # Webhook CRUD 测试
├── test_integration.py      # 上游集成客户端 mock 测试
├── test_clients.py          # engine 客户端单元测试（LLM/gateway/artifact/cowork/rag/webhook）
├── test_runner.py           # WorkflowRunner 执行路径测试
├── test_scheduler.py        # WorkflowScheduler 定时调度测试
├── test_registry.py         # 内置 Skill/Workflow 注册表测试
└── test_app_and_eventbus.py # App 生命周期 + EventBus 事件发布测试
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
| Workflow | `/workspace/{wsId}/workflow/{wfId}/canvas-layout` | PUT |
| Intent | `/workspace/{wsId}/intent/match` | POST |
| Intent | `/workspace/{wsId}/intent/commands` | GET |
| Intent | `/workspace/{wsId}/intent/run` | POST |
| Execution | `/workspace/{wsId}/task/pending` | GET |
| Execution | `/workspace/{wsId}/task/{taskId}/approve` | POST |
| Execution | `/workspace/{wsId}/task/{taskId}/deny` | POST |
| Execution | `/workspace/{wsId}/task/{taskId}/edit` | POST |
| Execution | `/workspace/{wsId}/execution/history` | GET |
| Execution | `/workspace/{wsId}/execution/{runId}` | GET |
| Execution | `/workspace/{wsId}/execution/export` | GET（json/csv，`?format=csv`） |
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
| Chat | `/workspace/{wsId}/agent/bind` | POST |
| Chat | `/workspace/{wsId}/agent/unbind` | POST |
| Chat | `/workspace/{wsId}/chat/run` | POST |

## 快速启动

```bash
cd /path/to/fusion-smallbusiness
source .venv/bin/activate

# 启动服务（默认端口 11490，可通过 FSB_SERVER_PORT 配置）
fusion-smallbusiness
# 或: uvicorn fsb.app:app --host 0.0.0.0 --port 11490

# 运行测试（307 用例，覆盖率 95%）
pytest tests/ -v

# 运行测试 + 覆盖率报告
pytest tests/ --cov=fsb --cov-report=term-missing -v
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
| fusion-studio | [#395](https://github.com/dahai80/fusion-studio/issues/395) | Workflow Canvas（React Flow）编辑器 — 对接 FSB canvas-layout API | 🟡 后端就绪，前端待开发 |
| fusion-agent-studio | [#274](https://github.com/dahai80/fusion-agent-studio/issues/274) | Chat↔FSB 集成 — Agent 绑定、自然语言工作流触发、运行通知端点 | 🟡 后端就绪，Chat 侧待开发 |

## 上游集成配置

FSB 通过 HTTP/JSON-RPC 客户端与上游服务通信，所有 URL 通过环境变量配置：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `FSB_ARTIFACTS_ENGINE_URL` | `http://127.0.0.1:11451` | fusion-artifacts-engine 服务地址 |
| `FSB_FUSION_MLX_URL` | `http://localhost:11432` | fusion-mlx LLM API 地址（经 fusion-gateway） |
| `FSB_FUSION_GATEWAY_URL` | `http://localhost:11444` | fusion-gateway 服务地址 |
| `FSB_FUSION_COWORK_URL` | `http://localhost:11437` | fusion-cowork RPC 地址 |
| `FSB_FUSION_CHAT_URL` | `http://127.0.0.1:11460` | fusion-chat / Agent 服务地址（Agent 绑定 + 运行完成通知） |
| `FSB_FUSION_RAG_URL` | `http://127.0.0.1:11436` | fusion-rag 知识库服务地址 |
| `FSB_FUSION_RAG_API_KEY` | _(空)_ | fusion-rag API Key（可选） |
| `FSB_LLM_DEFAULT_MODEL` | `default` | 默认 LLM 模型名 |
| `FSB_EMBEDDING_MODEL` | `BGE-M3` | 默认 Embedding 模型名 |
| `FSB_HTTP_TIMEOUT` | `10` | HTTP 请求超时（秒） |
| `FSB_STANDALONE_MODE` | `false` | 独立模式：true 时集成路由返回 stub 响应，且跳过租户/认证 + 限流中间件。默认 `false` 以保证生产安全；仅在 dev/test fail-soft 基线下设 `true`。 |
| `FSB_FUSION_IDENTITY_URL` | `http://127.0.0.1:11470` | fusion-identity JWT 校验端点（多租户认证） |
| `FSB_FUSION_IDENTITY_SERVICE_TOKEN` | _(空)_ | 调用 `POST /api/v1/auth/verify` 的服务令牌 |
| `FSB_AUTH_REQUIRE_JWT` | `true` | 非豁免路由是否强制校验 JWT（仅在非独立模式下生效） |
| `FSB_SECRET_KEY` | _(空)_ | 静态加密主密钥（连接器 auth 配置 + Webhook 密钥）。采用标准库信封加密（scrypt KDF + HMAC-SHA256 密钥流 XOR + encrypt-then-MAC）。为空时明文存储——生产环境务必设置强随机值。 |
| `FSB_RATE_LIMIT_CAPACITY` | `60` | 按租户令牌桶容量（最大突发请求数） |
| `FSB_RATE_LIMIT_REFILL` | `10` | 按租户令牌桶补充速率（token/秒） |
| `FSB_MAX_BODY_BYTES` | `2097152`（2 MiB） | POST/PUT/PATCH 请求体大小上限（超出返回 413） |
| `FSB_RUN_RETENTION_DAYS` | `30` | 运行历史留存窗口；每小时清理任务删除 `endTime` 早于此值的 run，并裁剪已结案的 pending task |
| `FSB_SCHEDULER_ENABLED` | `true` | 启用进程内 APScheduler cron 调度。设为 `false` 可让副本以 leader-only 模式运行（不本地调度），适用于多实例共享同一 DB 的场景 |
| `FSB_DB_PATH` | `fsb_data.db` | SQLite 数据库文件路径（生产环境请用绝对路径） |
| `FSB_DB_POOL_SIZE` | `8` | aiosqlite 连接池大小，支持并发 DB 访问。每个连接执行 `PRAGMA journal_mode=WAL` + `busy_timeout=5000`。`:memory:` DB 强制为 1（aiosqlite 内存库按连接隔离） |
| `FSB_DB_BACKEND` | `sqlite` | 存储后端选择器 —— `sqlite`（默认，单节点）或 `postgres`（多节点；需配 `FSB_PG_DSN`）。选 `postgres` 时，10 张领域表 + `run_traces` + 三张分布式原语表均以 JSONB 列 + 表达式索引创建 |
| `FSB_PG_DSN` | `""` | asyncpg 连接 DSN（如 `postgresql://user:pass@host:5432/db`）。`FSB_DB_BACKEND=postgres` 时必填 |
| `FSB_PG_POOL_SIZE` | `10` | Postgres 后端的 asyncpg 连接池大小 |
| `FSB_SCHEDULER_LEADER_TTL` | `30` | 调度器 leader 租约 TTL（秒）。仅租约持有者执行 cron 触发的工作流；副本在过期后重新竞争。由 `scheduler_lease` 表支撑 |
| `FSB_EVENT_DEDUP_TTL` | `120` | EventBus 分布式去重窗口（秒）。启用 Postgres 后端（或 `FSB_RATE_LIMIT_DISTRIBUTED=true`）时，事件 ID 通过 `event_dedup` 表跨节点去重，替代进程内字典 |
| `FSB_RATE_LIMIT_DISTRIBUTED` | `false` | 为 `true` 时，限流中间件从 `rate_limit_buckets` 表消费令牌（跨节点共享），而非每进程内存桶。DB 调用失败则回退本地桶 |

集成点说明：

- **OUTPUT_NODE** → `artifact_client` + `rag_client`：工作流产出自动创建 Artifact 并归档到知识库
- **SKILL_NODE** → `llm_client`：Skill 节点调用 LLM 执行，支持模型列表查询和 Embedding
- **CONNECTOR_NODE** → `gateway_client`：SaaS 连接器 Action 调用，支持 Connection 全生命周期管理 + OAuth2 授权流
- **APPROVAL_GATE_NODE** → `cowork_client`：审批闸通知推送到工作台 + 项目知识库同步/快照导入/空间导出

所有客户端在连接失败时优雅降级，不会阻塞工作流执行。

### 多租户认证（fusion-identity）

非独立模式下（`FSB_STANDALONE_MODE=false`），所有 `/workspace/{wsId}/*` 路由通过 [fusion-identity](https://github.com/dahai80/fusion-identity)（Fusion 生态唯一的 JWT 签发方与租户注册中心）进行认证：

- 每个非豁免请求需携带 `X-Tenant-Id` 头 + `Authorization: Bearer <JWT>`。
- JWT 通过 `POST {FSB_FUSION_IDENTITY_URL}/api/v1/auth/verify` 校验（由 `FSB_FUSION_IDENTITY_SERVICE_TOKEN` 网关控制）。
- JWT 的 `tid` 声明必须与 `X-Tenant-Id` 头一致（不一致返回 401）。
- 路径中的 `{wsId}` 绑定到已校验租户——访问其他租户的工作区返回 403。
- 已吊销的 token 返回 401。

独立模式（`FSB_STANDALONE_MODE=true`）下跳过认证中间件，路由无鉴权运行——与 fail-soft 开发/测试基线一致。该模式需显式开启，生产默认为 `false`。

> **生产部署：** 默认 `FSB_STANDALONE_MODE=false` 即开箱启用认证 + 限流。必须配置 `FSB_FUSION_IDENTITY_SERVICE_TOKEN`（以及可达的 `FSB_FUSION_IDENTITY_URL`），并设置强随机 `FSB_SECRET_KEY` 以开启密钥静态加密。仅在 dev/test fail-soft 基线下设 `FSB_STANDALONE_MODE=true`——严禁直接暴露到公网。

### 安全加固

- **密钥静态加密** —— 连接器 auth 配置与 Webhook 密钥在持久化前加密，采用纯标准库信封方案（`engine/secret_crypto`）：scrypt 密钥派生（N=16384, r=8, p=1, 64 MiB maxmem）→ HMAC-SHA256 密钥流 XOR → encrypt-then-MAC，base64 包装并加 `fsbenc1:` 前缀。主密钥为 `FSB_SECRET_KEY`；未设置时回退明文存储（记日志）。密钥仅在使用点（gateway 执行、Webhook 分发）解密，所有 API 响应中脱敏（`***` / 字段置空）。篡改或错误密钥的密文返回空并记日志，绝不抛异常。
- **限流与请求体大小** —— 按租户令牌桶中间件（`FSB_RATE_LIMIT_CAPACITY` / `FSB_RATE_LIMIT_REFILL`）限制请求速率（超限返回 429 + `Retry-After`），`FSB_MAX_BODY_BYTES` 拒绝超大的 POST/PUT/PATCH 请求体（413）。`/health`、`/docs`、`/openapi.json`、`/redoc` 免检。作为最外层中间件安装（先于认证运行），仅在非独立模式生效。
- **SSRF 防护** —— `api_call` 技能与 Webhook 注册/分发 URL 由共享的 `engine/url_guard` 校验：仅允许 `http`/`https` 协议，解析后的主机 IP 若为环回/私有/链路本地/保留/多播/未指定地址则一律拒绝。在技能执行与 Webhook 分发两条路径上均阻断云元数据（`169.254.169.254`）及内部服务 SSRF。`api_call` 执行与 Webhook 分发还会**钉住解析出的 IP** 发起出站请求（原主机名通过 `Host` 头保留），闭合校验与建连之间的 DNS rebinding TOCTOU 窗口。
- **事件总线租户隔离** —— 携带 `workspaceId` 的事件仅匹配该工作区名下的订阅（SQL `wsId` 谓词 + 客户端纵深过滤），杜绝跨租户工作流扇出。未携带 `workspaceId` 的事件仅入库不广播（跨租户扇出已禁用）。60 秒去重窗口与按事件类型的深度上限（最多 5 层）防止事件风暴与递归触发死循环。
- **数据库加固** —— SQLite 以 WAL 模式运行并设置 `busy_timeout=5000`；`list` 查询参数被钳制到 200 行分页上限（负值拒绝）；工作区级联删除为原子事务（显式 `BEGIN IMMEDIATE`）；`INSERT … ON CONFLICT` upsert 保留索引兄弟列；损坏的 JSON blob 逐行记录并跳过，不会拖垮整次查询。数据库路径可通过 `FSB_DB_PATH` 覆盖（生产环境请用绝对路径）。带过滤条件的查询（`title`、`status`、`eventType`、`enabled`）由 `json_extract` 表达式索引支撑。Schema 通过 `PRAGMA user_version` 版本化并配前向迁移注册表——新增索引在启动时自动应用，无需手动迁移。
- **工作区租户绑定** —— 非独立模式下，工作区创建/导入将工作区 id 绑定到调用方租户，列表按调用方租户过滤（不匹配返回 403）。
- **画布布局校验** —— `PUT .../canvas-layout` 拒绝非有限（`NaN`/`Infinity`）及非数值坐标，并在响应中返回未知节点 id。

### 外部路由鉴权守卫

`/external/*` 路由（工作流触发/状态、事件订阅、Webhook）在非独立模式下同样受租户守卫保护：

- 工作流触发/状态会解析工作流所属工作区，要求调用方租户拥有该工作区（否则 403）。
- 携带 `workspaceId` 的事件发布要求租户拥有该工作区。
- 订阅与 Webhook 的创建/删除为**管理员专属**（JWT `role` 必须为 `admin` 或 `owner`）。
- 订阅/Webhook 列表读取要求租户拥有被查询的工作区。
- 路由级 `require_tenant_present` 依赖在非独立模式下强制每个 `/external/*` 请求携带租户上下文，即使某 handler 遗漏内联归属校验也不会泄露跨租户数据。

### 生产部署与并发

- **共享 HTTP 连接池** —— 所有上游客户端（`llm`、`gateway`、`chat`、`artifact`、`cowork`、`rag`、`webhook`）共享单个 `httpx.AsyncClient` 连接池（`engine/http_pool`，最大 50 连接 / 20 keepalive），启动时创建、关闭时销毁。长耗时调用（embedding、批量上传、RAG ask）仍按请求传 `timeout=`，共享默认值不会抹掉它们的更长预算。消除了旧版每次请求 `async with httpx.AsyncClient()` 的 socket 抖动与连接数耗尽风险。
- **JWT 校验缓存** —— 对 fusion-identity 的 JWT 校验在进程内缓存 30 秒（最多 1024 条，FIFO 淘汰），以缓解上游 `verify_jwt` 在异步中间件中是同步 `httpx.post` 的问题。热点 token 命中缓存即纯字典查找；阻塞调用仅在缓存未命中或过期时触发。根因（异步中间件中的同步 verify）作为上游 fusion-core issue 跟踪。
- **僵尸 run 清理** —— 启动时对所有仍处于 `RUNNING` 状态的 run（崩溃/重启导致执行中断）分页扫描，标记为 `FAILED` 并写入 `endTime` + `reaped: stale RUNNING run after restart` 错误后持久化。否则崩溃的 run 会永远停在 `RUNNING`，阻塞 UI 与留存逻辑。
- **运行留存清理** —— 每小时任务（`fsb_retention_cleanup`）删除 `endTime` 早于 `FSB_RUN_RETENTION_DAYS`（默认 30）的 run，裁剪已结案的 pending task（approved/denied），并将事件裁剪到按工作区上限。启动时也会执行一次初始清理。以此限制长期运行部署的 DB 增长。
- **CAS resume 安全** —— `resume(run_id, decision)` 使用 compare-and-swap `UPDATE … WHERE json_extract(data,'$.status')='paused'`，两个并发 resume 调用方不会同时推进同一 run；失败方记录 lost-race 警告并返回，不会重复执行闸后分支。resume 前重新校验闸节点类型（工作流被编辑移除闸时快速失败，而非执行错误节点）。
- **调度器对账** —— 启动时从持久化工作流重建 cron 任务，并比对 expected-vs-registered 计数；不匹配记 error 而非静默丢失调度。多实例部署时在非 leader 副本上设置 `FSB_SCHEDULER_ENABLED=false` 以避免重复触发 cron。
- **DB 连接池** —— Store 维护 `FSB_DB_POOL_SIZE`（默认 8）个 aiosqlite 连接的池（`asyncio.Queue` 存放空闲连接，`acquire()`/`release()`）。每个 DB 操作都在 `async with store.acquire()` 内执行，并发工作流 + API 读取不再串行在单一连接上。每个连接以 `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` + `busy_timeout=5000` 打开。`:memory:` DB 强制 pool_size=1（aiosqlite 内存库按连接隔离）。`/health` 与 `/health/ready` 通过 `is_healthy()`（`SELECT 1`）探测连接池。
- **增量 run-trace 持久化** —— 节点执行 trace 存入独立的 `run_traces` 表（schema v3），而非每次 checkpoint 都把整段重序列化进 run blob。Runner 的 `_checkpoint(run, trace)` 写入常量大小的 run blob（`nodeTrace` 置空 `[]`）外加每节点一行 O(1) 的 `append_run_trace`，消除"每节点重序列化整个不断增长的 `RunInstance`"的 O(N²) 写放大。`get_run` / `list_runs` 从该表重新水合 `nodeTrace`（list 用 `WHERE runId IN (...)` 批量查询）。工作区删除与 run 留存清理在原子事务中级联删除对应 trace。

### 多节点 / 水平扩展

水平扩展部署（负载均衡后多副本 fsb）下，SQLite 无法跨写入者共享，故需启用 **Postgres 后端**：

1. **设置后端** —— `FSB_DB_BACKEND=postgres` + `FSB_PG_DSN=postgresql://user:pass@pg-host:5432/fsb`。启动时 `make_store()`（`db/__init__.py`）按后端选择；`PostgresStore`（asyncpg 连接池）镜像完整 `Store` API（10 张领域表、`run_traces`、`cas_run_status`、`find_matching_subscriptions`、`find_webhooks_for_event`、`cleanup_old_runs`），使用 JSONB 列与 `data->>'field'` 表达式索引。319 个 SQLite 测试保留为单节点基线；9 个 Postgres 集成测试（`tests/test_pg_store.py`）对活动 `fsb_test_autotest` 库运行（自动建/删库，无本地 Postgres 时跳过）。
2. **调度器 leader 选举** —— 仅一个副本应触发 cron 工作流。每个实例在 `scheduler_lease` 表持租约（`try_acquire_leader` / `renew_leader` / `is_leader` / `release_leader`）。启动时 `ensure_leadership()` 获取租约并按 `TTL/3` 调度续租任务；`_run_scheduled_workflow` 在非 leader 上提前返回。`FSB_SCHEDULER_LEADER_TTL`（默认 30s）控制过期。租约在进程崩溃后依然存活（已死持有者的行自然过期，另一副本重新获取）。
3. **EventBus 分布式去重** —— 模块级去重字典仅进程内有效。启用 Postgres 后端（或 `FSB_RATE_LIMIT_DISTRIBUTED=true`）时，`EventBus._is_duplicate` 委托给 `store.event_seen(eventId, wsId, TTL)`，由 `event_dedup` 表支撑（全局主键 + `seen_at` 清理扫描）。使副本 A 触发的事件在副本 B 跳过重复处理。DB 失败时回退内存字典。
4. **分布式限流** —— `FSB_RATE_LIMIT_DISTRIBUTED=true` 时，限流中间件从 `store.rate_limit_consume(tenant_key, capacity, refill)` 消费令牌，由 `rate_limit_buckets` 表支撑（按租户令牌桶，按 `last_refill` 起的墙钟时间补充）。跨副本给出一致的全局限流，而非 N 个独立的每进程桶。DB 失败时回退本地内存桶。

三个原语在**两种**后端均实现（SQLite 通过迁移 v4 获得相同表结构，单节点部署也得到该 API 表面），且在 standalone 单节点模式下默认为空操作 —— 仅当启用 Postgres 后端或对应 `FSB_*_DISTRIBUTED` 开关时激活。

应用启动时在 lifespan 中播种内置工作区（`fsb_ws_builtin`），写入 15 个内置 Skill 和 15 个内置 Workflow（稳定 ID、幂等），随后启动 APScheduler `AsyncIOScheduler` 并注册所有 `schedule.type == cron` 的现存工作流。通过 `/workflow/{wfId}/schedule` 设置的新 cron 调度会实时注册；删除调度则注销任务。失败优雅降级（仅记日志，非致命）。

### Workflow Canvas 布局（G10）

每个 `WorkflowNode` 携带 `position: {x, y}` 字段用于可视化布局。`PUT /workspace/{wsId}/workflow/{wfId}/canvas-layout`（body `{"layout": {nodeId: {x, y}}}`）将节点位置合并到图中以供可视化编辑器持久化。React Flow 前端在 [fusion-studio#395](https://github.com/dahai80/fusion-studio/issues/395) 跟踪。

### Chat 与 Agent 集成（G11）

FSB 提供 Chat↔FSB 双向集成（PRD §14.5 / §14.2）：

- `POST /workspace/{wsId}/agent/bind` / `/unbind` — 绑定/解绑 chat agent 到工作区（`bindAgentId`），同步到上游 chat 服务。非独立模式下仅管理员可操作。
- `POST /workspace/{wsId}/chat/run` — 自然语言查询 → 意图匹配 → 工作流运行（chat 驱动编排）。
- 运行完成时，若工作区已绑定 agent，FSB 向 `{FSB_FUSION_CHAT_URL}/api/v1/chat/notify` 推送 `run.completed`（fail-soft）。

Agent Studio / Chat 侧（通知端点、绑定/解绑端点、chat UI）在 [fusion-agent-studio#274](https://github.com/dahai80/fusion-agent-studio/issues/274) 跟踪。

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
cd /path/to/fusion-smallbusiness
source .venv/bin/activate
```

## 更新日志

### 0.2.0 (2026-10-26) — 企业级发布

在 0.2.0rc1 基础上修复 CI（issue #27）：

- CI 恢复绿色 — workflow 在可编辑安装前先安装固定版本 `fusion-core@v0.5.0`（此前失败：`fusion-core>=0.4.0` 不在 PyPI 上）。
- 相对 0.2.0rc1 无代码变更。

### 0.2.0rc1 (2026-09-04) — 企业级发布候选

**安全（P1，发布阻断项）：**
- Connector 查找修复 — `engine/runner.py` 按 `connectorKey` 解析真实 PK，正确传递 `connectionId`。
- 安全默认值 — 默认 `STANDALONE_MODE=false`、`AUTH_REQUIRE_JWT=true`；standalone 改为显式开启。
- SSRF 加固 — `webhook_dispatcher.py` 分发时重新执行 `resolve_pinned_url`，拒绝环回/重绑定，携带 `Host` 头。
- 密钥静态加密 — `engine/secret_crypto.py`（标准库 scrypt + HMAC 流密码，`fsbenc1:` 前缀）加密 webhook 密钥与 connector authConfig；环境变量 `FSB_SECRET_KEY`。
- 限流 + 请求体大小限制 — `RateLimitMiddleware`（令牌桶，按租户，超大写入返回 413）。

**性能（P2）：**
- DB 连接池（`_ConnectionPool`，`FSB_DB_POOL_SIZE=8`）替换单连接；40 并发写测试通过。
- O(1) 运行持久化 — `run_traces` 表 + `append_run_trace`；运行 blob 恒定大小（`nodeTrace=[]`），读取时重组。
- 运行保留定时任务（`FSB_RUN_RETENTION_DAYS=30`）防止 `runs`/`pending_tasks`/`events` 无限增长。
- `/health` 校验本地 DB；`/health/ready` 报告上游可达性（fail-soft，上游不可用 ≠ 实例不可用）。

**多节点就绪：**
- 可插拔存储后端 — `make_store()` 工厂，`FSB_DB_BACKEND`（默认 `sqlite`）；完整 asyncpg `PostgresStore` 对齐 `Store` API（10 表 + `run_traces` + 3 原语表，JSONB + 表达式索引）。
- 调度器 leader 选举 — `scheduler_lease` 表（双后端），TTL 租约 + TTL/3 续约任务，非 leader 提前返回。
- EventBus 分布式去重 — `event_dedup` 表在 PG 后端替换内存字典（`FSB_RATE_LIMIT_DISTRIBUTED`），DB 失败回退内存。
- 分布式限流 — `rate_limit_buckets` 表，middleware 在分布式模式委托存储。
- 新增环境变量：`FSB_DB_BACKEND`、`FSB_PG_DSN`、`FSB_PG_POOL_SIZE`、`FSB_SCHEDULER_LEADER_TTL`、`FSB_EVENT_DEDUP_TTL`、`FSB_RATE_LIMIT_DISTRIBUTED`。
- 9 个真实 Postgres 集成测试（无本地 PG 时跳过）。

**测试：** 328 通过（319 SQLite + 9 Postgres）。ruff clean。

### 0.1.4

- 初始 connector/skill/workflow 注册表、DAG 引擎、审批门、调度器、事件总线、fusion-identity 多租户鉴权。
