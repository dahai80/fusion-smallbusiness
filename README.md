# Fusion Small Business

[中文文档](README_CN.md)

Cross-SaaS intelligent business workspace for small business owners and teams.

## Product Positioning

Fusion Small Business (FSB) is a one-click business module within the Fusion Team/Enterprise subscription, providing:

- Visual drag-and-drop Workflow Canvas for building business workflows
- Third-party SaaS connectors + local file dual data sources
- Human approval gates for safety
- Automatic workflow output archiving to Fusion Project knowledge base

## Architecture

```
Connectors (Data Ingestion) → Skills (Atomic Capabilities) → Workflows (Business Pipelines)
```

Three-layer architecture with LangGraph-style DAG workflow engine, 7 node types:

- `START_NODE` / `END_NODE` — Flow boundaries
- `CONNECTOR_NODE` — SaaS connector invocation
- `SKILL_NODE` — LLM/function skills
- `CONDITION_NODE` — Conditional branching
- `APPROVAL_GATE_NODE` — Human approval gate (required for write operations)
- `OUTPUT_NODE` — Output generation

## Project Structure

```
src/fsb/
├── __init__.py              # Package entry
├── app.py                   # FastAPI app + lifecycle
├── models/
│   ├── common.py            # Enums, utils, shared models
│   ├── workspace.py         # Workspace model
│   ├── connector.py         # Connector model
│   ├── skill.py             # Skill model
│   ├── workflow.py          # Workflow + GraphDefinition models
│   ├── execution.py         # RunInstance + PendingTask models
│   ├── event.py             # EventTrigger + EventSubscription models
│   └── webhook.py           # Webhook model
├── db/
│   └── store.py             # SQLite async store (10 tables)
├── config.py                # Centralized upstream service URL config
├── engine/
│   ├── runner.py            # Workflow DAG execution engine (approval gates + webhook callbacks + upstream integration)
│   ├── router.py            # Intent routing (slash commands + fuzzy natural language matching)
│   ├── scheduler.py         # APScheduler cron scheduling
│   ├── event_bus.py         # Event-driven trigger engine
│   ├── webhook_dispatcher.py # Webhook HTTP callback dispatcher
│   ├── artifact_client.py   # fusion-artifacts-engine HTTP/JSON-RPC client (create/export/move-KB/list)
│   ├── llm_client.py        # fusion-mlx LLM API client
│   ├── gateway_client.py    # fusion-gateway connector HTTP client (Connection CRUD + OAuth2 flow)
│   ├── cowork_client.py     # fusion-cowork JSON-RPC 2.0 client (project KB sync/snapshot/export)
│   └── rag_client.py        # fusion-rag KB/retrieval/QA HTTP client
├── routes/
│   ├── workspace.py         # Workspace CRUD + import/export
│   ├── connector.py         # Connector connect/disconnect/refresh + metadata
│   ├── skill.py             # Skill CRUD + test
│   ├── workflow.py          # Workflow CRUD + run + schedule
│   ├── execution.py         # Execution history + approval actions
│   ├── integration.py       # Integration routes (canvas/project/artifact)
│   ├── external.py          # External triggers + events + webhooks
│   └── variable.py          # Variables + templates
├── skills/
│   └── registry.py          # 15 built-in skill definitions
└── workflows/
    └── registry.py          # 15 built-in workflow definitions

tests/
├── conftest.py              # pytest fixtures
├── test_api.py              # API integration tests
├── test_api_extended.py     # Extended API endpoint tests (404/502/approval/integration/external)
├── test_engine.py           # Engine + DAG validation tests
├── test_event.py            # Event trigger + subscription tests
├── test_webhook.py          # Webhook CRUD tests
├── test_integration.py      # Upstream integration client mock tests
├── test_clients.py          # Engine client unit tests (LLM/gateway/artifact/cowork/rag/webhook)
├── test_runner.py           # WorkflowRunner execution path tests
├── test_scheduler.py        # WorkflowScheduler scheduling tests
├── test_registry.py         # Built-in Skill/Workflow registry tests
└── test_app_and_eventbus.py # App lifecycle + EventBus tests
```

## API Endpoints

All endpoints prefixed with `/api/v1/fsb`

| Module | Endpoint | Method |
|--------|----------|--------|
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

## Quick Start

```bash
cd /path/to/fusion-smallbusiness
source .venv/bin/activate

# Start the server (default port 11456, configurable via FSB_SERVER_PORT)
fusion-smallbusiness
# or: uvicorn fsb.app:app --host 0.0.0.0 --port 11456

# Run tests (291 tests, 95% coverage)
pytest tests/ -v

# Run tests with coverage report
pytest tests/ --cov=fsb --cov-report=term-missing -v
```

## Built-in Skills (15)

| Skill | Description |
|-------|-------------|
| cash-flow-snapshot | Cash flow snapshot |
| draft-invoice-reminder | Invoice reminder email generation |
| score-lead | Lead scoring |
| weekly-sales-report | Weekly sales report |
| expense-categorize | Expense categorization |
| customer-sentiment | Customer sentiment analysis |
| contract-summary | Contract key points extraction |
| tax-reminder | Tax deadline reminder |
| email-draft | Email drafting |
| inventory-alert | Inventory alert |
| payroll-summary | Payroll summary |
| competitor-brief | Competitor brief |
| slack-digest | Slack digest |
| invoice-validate | Invoice validation |
| kpi-dashboard-data | KPI dashboard data |

## Built-in Workflows (15)

| Workflow | Slash Command | Description |
|----------|---------------|-------------|
| invoice-chase | `/invoice-chase` | Overdue invoice chasing |
| lead-nurture | `/lead-nurture` | Lead nurturing follow-up |
| cash-flow-alert | `/cash-flow-alert` | Cash flow alert (weekly cron) |
| weekly-sales | `/weekly-sales` | Weekly sales report |
| expense-review | `/expense-review` | Expense review |
| customer-health | `/customer-health` | Customer health check |
| contract-review | `/contract-review` | Contract review |
| tax-filing-reminder | `/tax-reminder` | Tax filing reminder (monthly cron) |
| inventory-check | `/inventory-check` | Inventory check alert (weekday cron) |
| payroll-process | `/payroll` | Payroll processing (monthly cron) |
| slack-daily-digest | `/slack-digest` | Slack daily digest (weekday cron) |
| invoice-validation | `/invoice-validate` | Invoice compliance validation |
| kpi-dashboard | `/kpi` | KPI dashboard update (weekday cron) |
| competitor-watch | `/competitor-watch` | Competitor monitoring (weekly cron) |
| multi-channel-outreach | `/outreach` | Multi-channel outreach |

## Upstream Dependency Issues

FSB depends on the following upstream modules, tracked via issues:

| Upstream Module | Issue | Request | Status |
|-----------------|-------|---------|--------|
| fusion-gateway | [#2](https://github.com/dahai80/fusion-gateway/issues/2) | Connector plugin framework, OAuth2 delegation, unified Action API, audit log | ✅ Integrated |
| fusion-gateway | [#6](https://github.com/dahai80/fusion-gateway/issues/6) | OAuth2 authorization flow + credential persistence + real SaaS API calls | ✅ Integrated |
| fusion-gateway | [#7](https://github.com/dahai80/fusion-gateway/issues/7) | OAuth2 Provider + Token Refresh + AES encryption | ✅ Integrated |
| fusion-gateway | [#8](https://github.com/dahai80/fusion-gateway/issues/8) | HTTPS termination + AES encryption at rest | ✅ Integrated |
| fusion-cowork | [#7](https://github.com/dahai80/fusion-cowork/issues/7) | desk.project.syncKnowledge — project KB sync | ✅ Integrated |
| fusion-cowork | [#8](https://github.com/dahai80/fusion-cowork/issues/8) | desk.project.importSnapshot — session snapshot import | ✅ Integrated |
| fusion-cowork | [#9](https://github.com/dahai80/fusion-cowork/issues/9) | desk.project.exportToProject — export workspace content to project | ✅ Integrated |
| fusion-agent-studio | [#35](https://github.com/dahai80/fusion-agent-studio/issues/35) | LangGraph workflow engine, approval gate breakpoints, context sandbox, Skill registration/execution | ✅ Integrated |
| fusion-cowork | [#4](https://github.com/dahai80/fusion-cowork/issues/4) | Sidebar entry, workspace session isolation, permission model reuse, approval notification push | ✅ Integrated |
| fusion-studio | [#28](https://github.com/dahai80/fusion-studio/issues/28) | Frontend route/page registration, Canvas component reuse, Workflow Canvas integration | ✅ Integrated (Plugin) |
| fusion-artifacts-engine | [#18](https://github.com/dahai80/fusion-artifacts-engine/issues/18) | Workflow output → Artifact creation API, Artifact reverse-input to workflow | ✅ Integrated |
| fusion-rag | [#27](https://github.com/dahai80/fusion-rag/issues/27) | Output auto-archiving to Project KB, RAG retrieval for workflow context loading | ✅ Integrated |
| fusion-mlx | [#302](https://github.com/dahai80/fusion-mlx/issues/302) | Non-admin model management API, model capability tags, standalone embedding model config | ✅ Integrated |

## Upstream Integration Config

FSB communicates with upstream services via HTTP/JSON-RPC clients. All URLs are configured through environment variables:

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `FSB_ARTIFACTS_ENGINE_URL` | `http://127.0.0.1:11451` | fusion-artifacts-engine service URL |
| `FSB_FUSION_MLX_URL` | `http://localhost:11434` | fusion-mlx LLM API URL |
| `FSB_FUSION_GATEWAY_URL` | `http://localhost:11444` | fusion-gateway service URL |
| `FSB_FUSION_COWORK_URL` | `http://localhost:11437` | fusion-cowork RPC URL |
| `FSB_FUSION_RAG_URL` | `http://127.0.0.1:11436` | fusion-rag KB service URL |
| `FSB_FUSION_RAG_API_KEY` | _(empty)_ | fusion-rag API Key (optional) |
| `FSB_LLM_DEFAULT_MODEL` | `default` | Default LLM model name |
| `FSB_EMBEDDING_MODEL` | `BGE-M3` | Default embedding model name |
| `FSB_HTTP_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `FSB_STANDALONE_MODE` | `true` | Standalone mode: when true, integration routes return stub responses to avoid errors when upstream is unavailable |

Integration points:

- **OUTPUT_NODE** → `artifact_client` + `rag_client`: Workflow output auto-creates Artifacts and archives to knowledge base
- **SKILL_NODE** → `llm_client`: Skill node calls LLM, supports model listing and embedding
- **CONNECTOR_NODE** → `gateway_client`: SaaS connector Action calls, full Connection lifecycle + OAuth2 authorization flow
- **APPROVAL_GATE_NODE** → `cowork_client`: Approval gate notifications pushed to workspace + project KB sync/snapshot import/workspace export

All clients gracefully degrade on connection failure and never block workflow execution.

## fusion-studio Plugin

FSB provides frontend integration via the fusion-studio Plugin mechanism:

```
~/.fusion-studio/plugins/fsb.fusion/
├── manifest.json    # Plugin metadata
└── main.py          # Entry (on_load/on_render_panel)
```

The plugin provides three panels:

- **Dashboard** — Workspace overview, health status, quick actions
- **Run Workflow** — Workflow list and one-click trigger
- **Pending Approvals** — Pending task list with Approve/Deny actions

## Design Docs

- [PRD & Plan Document](../architecture/fusion-smallbusiness-prd-plan.md)

## Environment Setup

```bash
cd /path/to/fusion-smallbusiness
source .venv/bin/activate
```
