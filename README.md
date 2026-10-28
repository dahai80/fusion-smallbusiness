# Fusion Small Business

[中文文档](README_CN.md)

> **Version 0.2.1** — Enterprise release. Single-node + multi-node (Postgres) production-ready. See [Changelog](#changelog).

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
├── seed.py                  # Builtin skills/workflows seeding in app lifespan
├── auth.py                  # fusion-identity JWT verify
├── tenant_dep.py            # Tenant ownership + admin-role guards
├── engine/
│   ├── runner.py            # Workflow DAG execution engine (approval gates + webhook callbacks + upstream integration + chat notify)
│   ├── router.py            # Intent routing (slash commands + fuzzy natural language matching)
│   ├── expr.py              # Safe AST-based condition expression evaluator
│   ├── chat_client.py       # fusion-chat HTTP client (agent bind/unbind + run-completion notify, fail-soft)
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
│   ├── workflow.py          # Workflow CRUD + run + schedule + canvas layout
│   ├── execution.py         # Execution history + approval actions + CSV export
│   ├── intent.py            # Intent match / commands / run routes
│   ├── integration.py       # Integration routes (canvas/project/artifact)
│   ├── external.py          # External triggers + events + webhooks (tenant-guarded)
│   ├── chat.py              # Agent bind/unbind + chat-driven workflow run
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
| Workflow | `/workspace/{wsId}/workflow/{wfId}/canvas-layout` | PUT |
| Intent | `/workspace/{wsId}/intent/match` | POST |
| Intent | `/workspace/{wsId}/intent/match` | POST |
| Intent | `/workspace/{wsId}/intent/commands` | GET |
| Intent | `/workspace/{wsId}/intent/run` | POST |
| Execution | `/workspace/{wsId}/task/pending` | GET |
| Execution | `/workspace/{wsId}/task/{taskId}/approve` | POST |
| Execution | `/workspace/{wsId}/task/{taskId}/deny` | POST |
| Execution | `/workspace/{wsId}/task/{taskId}/edit` | POST |
| Execution | `/workspace/{wsId}/execution/history` | GET |
| Execution | `/workspace/{wsId}/execution/{runId}` | GET |
| Execution | `/workspace/{wsId}/execution/export` | GET (json/csv via `?format=csv`) |
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

## Quick Start

```bash
cd /path/to/fusion-smallbusiness
source .venv/bin/activate

# Start the server (default port 11490, configurable via FSB_SERVER_PORT)
fusion-smallbusiness
# or: uvicorn fsb.app:app --host 0.0.0.0 --port 11490

# Run tests (307 tests, 95% coverage)
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
| fusion-studio | [#395](https://github.com/dahai80/fusion-studio/issues/395) | Workflow Canvas (React Flow) editor — consume FSB canvas-layout API | 🟡 Backend ready, frontend pending |
| fusion-agent-studio | [#274](https://github.com/dahai80/fusion-agent-studio/issues/274) | Chat↔FSB integration — agent bind, NL workflow trigger, run-notify endpoint | 🟡 Backend ready, chat side pending |

## Upstream Integration Config

FSB communicates with upstream services via HTTP/JSON-RPC clients. All URLs are configured through environment variables:

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `FSB_ARTIFACTS_ENGINE_URL` | `http://127.0.0.1:11451` | fusion-artifacts-engine service URL |
| `FSB_FUSION_MLX_URL` | `http://localhost:11432` | fusion-mlx LLM API URL (via fusion-gateway) |
| `FSB_FUSION_GATEWAY_URL` | `http://localhost:11444` | fusion-gateway service URL |
| `FSB_FUSION_COWORK_URL` | `http://localhost:11437` | fusion-cowork RPC URL |
| `FSB_FUSION_CHAT_URL` | `http://127.0.0.1:11460` | fusion-chat / agent service URL (agent bind + run-completion notify) |
| `FSB_FUSION_RAG_URL` | `http://127.0.0.1:11436` | fusion-rag KB service URL |
| `FSB_FUSION_RAG_API_KEY` | _(empty)_ | fusion-rag API Key (optional) |
| `FSB_LLM_DEFAULT_MODEL` | `default` | Default LLM model name |
| `FSB_EMBEDDING_MODEL` | `BGE-M3` | Default embedding model name |
| `FSB_HTTP_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `FSB_STANDALONE_MODE` | `false` | Standalone mode: when true, integration routes return stub responses AND tenant/auth + rate-limit middleware is skipped. Default `false` for production safety; set `true` only for the dev/test fail-soft baseline. |
| `FSB_FUSION_IDENTITY_URL` | `http://127.0.0.1:11470` | fusion-identity JWT verify endpoint (multi-tenant auth) |
| `FSB_FUSION_IDENTITY_SERVICE_TOKEN` | _(empty)_ | service token gating `POST /api/v1/auth/verify` |
| `FSB_AUTH_REQUIRE_JWT` | `true` | require valid JWT on all non-exempt routes (non-standalone mode only) |
| `FSB_SECRET_KEY` | _(empty)_ | master key for secret encryption-at-rest (connector auth config + webhook secrets). Uses stdlib envelope encryption (scrypt KDF + HMAC-SHA256 keystream XOR + encrypt-then-MAC). When empty, secrets are stored in plaintext — set a strong random value in production. |
| `FSB_RATE_LIMIT_CAPACITY` | `60` | per-tenant token-bucket capacity (max burst of in-flight requests) |
| `FSB_RATE_LIMIT_REFILL` | `10` | per-tenant token-bucket refill rate (tokens/second) |
| `FSB_MAX_BODY_BYTES` | `2097152` (2 MiB) | request body size ceiling for POST/PUT/PATCH (413 on overflow) |
| `FSB_RUN_RETENTION_DAYS` | `30` | run history retention window; the hourly cleanup job deletes runs whose `endTime` is older than this and trims resolved pending tasks |
| `FSB_SCHEDULER_ENABLED` | `true` | enable the in-process APScheduler cron dispatcher. Set `false` to run a replica in leader-only mode (no local scheduling) when multiple fsb instances share one DB |
| `FSB_DB_PATH` | `fsb_data.db` | SQLite database file path (use an absolute path in production) |
| `FSB_DB_POOL_SIZE` | `8` | aiosqlite connection pool size for concurrent DB access. Each connection runs `PRAGMA journal_mode=WAL` + `busy_timeout=5000`. Forced to 1 for `:memory:` DBs (aiosqlite isolates in-memory DBs per connection). |
| `FSB_DB_BACKEND` | `sqlite` | storage backend selector — `sqlite` (default, single-node) or `postgres` (multi-node; requires `FSB_PG_DSN`). When `postgres`, all 10 domain tables + `run_traces` + the three distributed-primitive tables are created with JSONB columns and expression indexes. |
| `FSB_PG_DSN` | `""` | asyncpg connection DSN (e.g. `postgresql://user:pass@host:5432/db`). Required when `FSB_DB_BACKEND=postgres`. |
| `FSB_PG_POOL_SIZE` | `10` | asyncpg connection pool size for the Postgres backend. |
| `FSB_SCHEDULER_LEADER_TTL` | `30` | scheduler leader-lease TTL in seconds. Only the lease holder executes cron-triggered workflows; replicas re-acquire on expiry. Backed by the `scheduler_lease` table on the configured backend. |
| `FSB_EVENT_DEDUP_TTL` | `120` | EventBus distributed dedup window in seconds. When the Postgres backend (or `FSB_RATE_LIMIT_DISTRIBUTED=true`) is active, event IDs are deduped across nodes via the `event_dedup` table instead of the in-process dict. |
| `FSB_RATE_LIMIT_DISTRIBUTED` | `false` | when `true`, the rate-limit middleware consumes tokens from the `rate_limit_buckets` table (shared across nodes) instead of the per-process in-memory bucket. Falls back to local buckets if the DB call fails. |

Integration points:

- **OUTPUT_NODE** → `artifact_client` + `rag_client`: Workflow output auto-creates Artifacts and archives to knowledge base
- **SKILL_NODE** → `llm_client`: Skill node calls LLM, supports model listing and embedding
- **CONNECTOR_NODE** → `gateway_client`: SaaS connector Action calls, full Connection lifecycle + OAuth2 authorization flow
- **APPROVAL_GATE_NODE** → `cowork_client`: Approval gate notifications pushed to workspace + project KB sync/snapshot import/workspace export

All clients gracefully degrade on connection failure and never block workflow execution.

### Multi-tenant authentication (fusion-identity)

In non-standalone mode (`FSB_STANDALONE_MODE=false`), all `/workspace/{wsId}/*` routes require authentication via [fusion-identity](https://github.com/dahai80/fusion-identity) (the sole JWT issuer + tenant registry for the Fusion ecosystem):

- Every non-exempt request must carry `X-Tenant-Id` header + `Authorization: Bearer <JWT>`.
- The JWT is verified against `POST {FSB_FUSION_IDENTITY_URL}/api/v1/auth/verify` (gated by `FSB_FUSION_IDENTITY_SERVICE_TOKEN`).
- JWT `tid` claim must match the `X-Tenant-Id` header (401 on mismatch).
- The path `{wsId}` is bound to the verified tenant — accessing another tenant's workspace returns 403.
- Revoked tokens are rejected with 401.

In standalone mode (`FSB_STANDALONE_MODE=true`) the auth middleware is skipped, so routes run unguarded — matching the fail-soft development/testing baseline. This is opt-in only; the production default is `false`.

> **Production deployment:** the default `FSB_STANDALONE_MODE=false` enables auth + rate-limiting out of the box. You MUST provision `FSB_FUSION_IDENTITY_SERVICE_TOKEN` (and a reachable `FSB_FUSION_IDENTITY_URL`) and set a strong `FSB_SECRET_KEY` for secret encryption-at-rest. Set `FSB_STANDALONE_MODE=true` only for the dev/test fail-soft baseline — it must not be exposed publicly.

### Security hardening

- **Secret encryption-at-rest** — connector auth config and webhook secrets are encrypted before persistence using a stdlib-only envelope scheme (`engine/secret_crypto`): scrypt key derivation (N=16384, r=8, p=1, 64 MiB maxmem) → HMAC-SHA256 keystream XOR → encrypt-then-MAC, base64-wrapped with the `fsbenc1:` prefix. The master key is `FSB_SECRET_KEY`; when unset, secrets fall back to plaintext storage (logged). Secrets are decrypted only at use sites (gateway execute, webhook dispatch) and redacted (`***` / blanked fields) from all API responses. Tampered or wrong-key ciphertext returns empty and is logged, never raises.
- **Rate limiting & body size** — a per-tenant token-bucket middleware (`FSB_RATE_LIMIT_CAPACITY` / `FSB_RATE_LIMIT_REFILL`) caps request rate (429 + `Retry-After` on overflow), and `FSB_MAX_BODY_BYTES` rejects oversized POST/PUT/PATCH bodies with 413. `/health`, `/docs`, `/openapi.json`, `/redoc` are exempt. Installed as the outermost middleware (runs before auth), active only in non-standalone mode.
- **SSRF guard** — `api_call` skills and webhook registration/dispatch URLs are validated by a shared `engine/url_guard` helper: only `http`/`https` schemes are allowed, and the resolved host IP is rejected if it is loopback, private, link-local, reserved, multicast, or unspecified. This blocks cloud-metadata (`169.254.169.254`) and internal-service SSRF on both the skill-execution and webhook-dispatch paths. `api_call` execution and webhook dispatch additionally **pin the resolved IP** for the outbound request (original host preserved via the `Host` header), closing the DNS-rebinding TOCTOU window between validation and connection.
- **EventBus tenant scoping** — events carrying a `workspaceId` only match subscriptions owned by that workspace (SQL `wsId` predicate + client-side defense-in-depth filter), preventing cross-tenant workflow fan-out. Events without a `workspaceId` are stored but never broadcast (cross-tenant fan-out disabled). A 60s dedup window and per-event-type depth limit (max 5) prevent event storms and recursive trigger loops.
- **DB hardening** — SQLite runs in WAL mode with `busy_timeout=5000`; `list` query params are clamped to a 200-row page ceiling (negatives rejected); workspace cascade delete is atomic (single transaction via explicit `BEGIN IMMEDIATE`); `INSERT … ON CONFLICT` upsert preserves indexed sibling columns; corrupt JSON blobs are logged and skipped per-row rather than failing the whole query. The DB path is overridable via `FSB_DB_PATH` (use an absolute path in production). Filtered queries (`title`, `status`, `eventType`, `enabled`) are backed by `json_extract` expression indexes. Schema is versioned via `PRAGMA user_version` with a forward-only migration registry — new indexes apply automatically on startup without a manual migration step.
- **Workspace tenant binding** — in non-standalone mode, workspace create/import bind the workspace id to the caller's tenant, and list is scoped to the caller tenant (403 on mismatch).
- **Canvas-layout validation** — `PUT .../canvas-layout` rejects non-finite (`NaN`/`Infinity`) and non-numeric positions, and reports unknown node ids in the response.

### External route auth guard

The `/external/*` routes (workflow trigger/status, event subscriptions, webhooks) are also tenant-guarded in non-standalone mode:

- Workflow trigger/status resolve the workflow's owning workspace and require the caller tenant to own it (403 otherwise).
- Event posting with a `workspaceId` requires tenant ownership of that workspace.
- Subscription and webhook create/delete are **admin-only** (JWT `role` must be `admin` or `owner`).
- Subscription/webhook list reads require tenant ownership of the queried workspace.
- A router-level `require_tenant_present` dependency enforces that every `/external/*` request carries a tenant context in non-standalone mode, so a handler that forgets an inline ownership check cannot leak cross-tenant data.

### Production deployment & concurrency

- **Shared HTTP connection pool** — all upstream clients (`llm`, `gateway`, `chat`, `artifact`, `cowork`, `rag`, `webhook`) share a single `httpx.AsyncClient` pool (`engine/http_pool`, 50 max connections / 20 keepalive) created at startup and closed on shutdown. Per-request `timeout=` is still passed for long-running calls (embeddings, batch upload, RAG ask) so the shared default does not erase their longer budgets. This eliminates the per-call socket churn and connection-limit-exhaustion risk of the old `async with httpx.AsyncClient()` per request pattern.
- **JWT verify cache** — JWT verification against fusion-identity is cached in-process for 30s (max 1024 entries, FIFO eviction) to mitigate the upstream `verify_jwt` being a synchronous `httpx.post` inside the async middleware. A hot token hits the cache as a pure dict lookup; the blocking call only fires on cache miss or expiry. The root cause (sync verify in async middleware) is tracked as an upstream fusion-core issue.
- **Stale-run reaper** — on startup, any run left in `RUNNING` status (killed mid-execution by a crash/restart) is paginated, marked `FAILED` with an `endTime` + `reaped: stale RUNNING run after restart` error, and persisted. Without this a crashed run stays `RUNNING` forever and blocks UI/retention logic.
- **Run retention cleanup** — an hourly job (`fsb_retention_cleanup`) deletes runs whose `endTime` is older than `FSB_RUN_RETENTION_DAYS` (default 30), prunes resolved pending tasks (approved/denied), and trims events to a per-workspace ceiling. An initial cleanup also runs at startup. This bounds DB growth in long-running deployments.
- **CAS resume safety** — `resume(run_id, decision)` uses a compare-and-swap `UPDATE … WHERE json_extract(data,'$.status')='paused'` so two concurrent resume callers cannot both advance the run; the loser logs a lost-race warning and returns without double-executing the post-gate branch. The gate node type is re-validated before resume (a workflow edited to remove the gate fails fast rather than executing the wrong node).
- **Scheduler reconciliation** — cron jobs are rebuilt from persisted workflows on startup with an expected-vs-registered counter; a mismatch logs an error rather than silently losing schedules. In multi-instance deployments set `FSB_SCHEDULER_ENABLED=false` on non-leader replicas to avoid duplicate cron firing.
- **DB connection pool** — the Store maintains a pool of `FSB_DB_POOL_SIZE` (default 8) aiosqlite connections (an `asyncio.Queue` of idle connections with `acquire()`/`release()`). Every DB operation runs inside `async with store.acquire()`, so concurrent workflows + API reads no longer serialize on a single connection. Each connection is opened with `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` + `busy_timeout=5000`. `:memory:` DBs force pool_size=1 (aiosqlite isolates in-memory DBs per connection). `/health` and `/health/ready` probe the pool via `is_healthy()` (`SELECT 1`).
- **Incremental run-trace persistence** — node execution traces are stored in a dedicated `run_traces` table (schema v3), not re-serialized into the run blob on every checkpoint. The runner's `_checkpoint(run, trace)` writes a constant-size run blob (`nodeTrace` stripped to `[]`) plus one O(1) `append_run_trace` row per node, eliminating the O(N²) write amplification of re-serializing the whole growing `RunInstance` per node. `get_run` / `list_runs` re-hydrate `nodeTrace` from the table (batched `WHERE runId IN (...)` for list). Workspace deletion and run retention cascade-delete traces atomically with their runs.

### Multi-node / horizontal scaling

For horizontally-scaled deployments (multiple fsb replicas behind a load balancer), SQLite cannot be shared across writers, so the **Postgres backend** is required:

1. **Set the backend** — `FSB_DB_BACKEND=postgres` + `FSB_PG_DSN=postgresql://user:pass@pg-host:5432/fsb`. `make_store()` (`db/__init__.py`) selects the backend at startup; `PostgresStore` (asyncpg pool) mirrors the full `Store` API (all 10 domain tables, `run_traces`, `cas_run_status`, `find_matching_subscriptions`, `find_webhooks_for_event`, `cleanup_old_runs`) using JSONB columns and `data->>'field'` expression indexes. The 319 SQLite tests remain the single-node baseline; 9 Postgres integration tests (`tests/test_pg_store.py`) run against a live `fsb_test_autotest` database (auto-created/dropped, skipped when no local Postgres).
2. **Scheduler leader election** — only one replica should fire cron workflows. Each instance holds a lease in the `scheduler_lease` table (`try_acquire_leader` / `renew_leader` / `is_leader` / `release_leader`). On startup `ensure_leadership()` acquires the lease and schedules a renewal job at `TTL/3`; `_run_scheduled_workflow` early-returns on non-leaders. `FSB_SCHEDULER_LEADER_TTL` (default 30s) controls expiry. Leases survive process crashes (a dead holder's row simply expires and another replica re-acquires).
3. **EventBus distributed dedup** — the module-global dedup dict only works within one process. On the Postgres backend (or `FSB_RATE_LIMIT_DISTRIBUTED=true`), `EventBus._is_duplicate` delegates to `store.event_seen(eventId, wsId, TTL)` backed by the `event_dedup` table (global primary key + `seen_at` cleanup sweep). This makes an event fired on replica A skip re-processing on replica B. Falls back to the in-memory dict on any DB failure.
4. **Distributed rate limit** — with `FSB_RATE_LIMIT_DISTRIBUTED=true`, the rate-limit middleware consumes tokens from `store.rate_limit_consume(tenant_key, capacity, refill)` backed by `rate_limit_buckets` (per-tenant token bucket, refilled by elapsed wall-clock since `last_refill`). This gives a coherent global limit across replicas instead of N independent per-process buckets. Falls back to the local in-memory bucket on DB failure.

All three primitives are implemented on **both** backends (SQLite gets the same table schema via migration v4, so single-node deployments gain the API surface too) and are no-ops-by-default in standalone single-node mode — they activate only when the Postgres backend or the corresponding `FSB_*_DISTRIBUTED` flag is set.

On startup the app lifespan seeds a builtin workspace (`fsb_ws_builtin`) with the 15 built-in skills and 15 built-in workflows (stable IDs, idempotent), then starts the APScheduler `AsyncIOScheduler` and registers every existing workflow whose `schedule.type == cron`. New cron schedules set via `/workflow/{wfId}/schedule` are registered live; schedule deletion unregisters the job. Failures degrade gracefully (logged, non-fatal).

### Workflow Canvas layout (G10)

Each `WorkflowNode` carries a `position: {x, y}` field for visual layout. `PUT /workspace/{wsId}/workflow/{wfId}/canvas-layout` (body `{"layout": {nodeId: {x, y}}}`) merges node positions onto the graph for persistence by the visual editor. The React Flow frontend is tracked in [fusion-studio#395](https://github.com/dahai80/fusion-studio/issues/395).

### Chat & Agent integration (G11)

FSB exposes a Chat↔FSB bidirectional integration (PRD §14.5 / §14.2):

- `POST /workspace/{wsId}/agent/bind` / `/unbind` — bind/unbind a chat agent to the workspace (`bindAgentId`), synced to the chat service upstream. Admin-only in non-standalone mode.
- `POST /workspace/{wsId}/chat/run` — natural-language query → intent match → workflow run (chat-driven orchestration).
- On run completion, if the workspace has a bound agent, FSB posts `run.completed` to `{FSB_FUSION_CHAT_URL}/api/v1/chat/notify` (fail-soft).

The Agent Studio / Chat side (notify endpoint, bind/unbind endpoints, chat UI) is tracked in [fusion-agent-studio#274](https://github.com/dahai80/fusion-agent-studio/issues/274).

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

## Changelog

### 0.2.1 (2026-10-28) — Patch Release

Process title + config governance (issues #29, #30):

- Process title — `ps`/Activity Monitor now shows `fusion-smallbusiness serve :11490` instead of bare `Python`, via `fusion_core.proc.set_process_title` (safe fallback when `setproctitle` is missing).
- Config single-point resolution (config Phase 2.2) — adopts `fusion_core.config` helpers: `FUSION_GATEWAY_BASE_URL` (canonical gateway address), `FUSION_SMALLBUSINESS_PORT`, `FUSION_SMALLBUSINESS_DATA_DIR`. Legacy `FSB_*` env vars still honored as fallback — no behavior change.
- LLM calls now authenticate with `FUSION_CLIENT_KEY` (`Authorization: Bearer`) resolved via `fusion_core.config.client_key()` — dev missing key = anonymous + warning; `FUSION_PROFILE=prod` missing key = RuntimeError.
- Dependency: `fusion-core>=0.7.0`, `setproctitle>=1.3.0`; CI pins `fusion-core@v0.7.0`.

### 0.2.0 (2026-10-26) — Enterprise Release

Finalizes 0.2.0rc1 with CI fix (issue #27):

- CI green again — workflow installs pinned `fusion-core@v0.5.0` from GitHub before editable install (was failing: `fusion-core>=0.4.0` not on PyPI).
- No code changes vs 0.2.0rc1.

### 0.2.0rc1 (2026-09-04) — Enterprise Release Candidate

**Security (P1, release-blocking):**
- Connector lookup fix — `engine/runner.py` resolves Connector by real PK via `connectorKey`, correct `connectionId` propagation.
- Secure defaults — `STANDALONE_MODE=false`, `AUTH_REQUIRE_JWT=true` by default; standalone is now an explicit opt-in.
- SSRF hardening — `webhook_dispatcher.py` re-runs `resolve_pinned_url` at dispatch time, refuses loopback/rebind, sends `Host` header.
- Secrets encryption-at-rest — `engine/secret_crypto.py` (stdlib scrypt + HMAC stream cipher, `fsbenc1:` prefix) for webhook secrets and connector authConfig; `FSB_SECRET_KEY` env.
- Rate limiting + body-size limits — `RateLimitMiddleware` (token bucket, per-tenant, 413 on oversized ingestion).

**Performance (P2):**
- DB connection pool (`_ConnectionPool`, `FSB_DB_POOL_SIZE=8`) replaces single shared connection; 40-parallel-write concurrency test green.
- O(1) run persistence — `run_traces` table + `append_run_trace`; run blob stays constant-size (`nodeTrace=[]`), re-hydrated on read.
- Run retention scheduled job (`FSB_RUN_RETENTION_DAYS=30`) prevents unbounded `runs`/`pending_tasks`/`events` growth.
- `/health` verifies local DB; `/health/ready` reports upstream reachability (fail-soft, upstream down ≠ instance down).

**Multi-node readiness:**
- Pluggable storage backend — `make_store()` factory, `FSB_DB_BACKEND` (default `sqlite`); full asyncpg `PostgresStore` mirrors the `Store` API (10 tables + `run_traces` + 3 primitive tables, JSONB + expression indexes).
- Scheduler leader election — `scheduler_lease` table (both backends), TTL lease + TTL/3 renewal job, non-leader early-return.
- EventBus distributed dedup — `event_dedup` table replaces in-memory dict on PG backend (`FSB_RATE_LIMIT_DISTRIBUTED`), in-memory fallback.
- Distributed rate limit — `rate_limit_buckets` table, middleware delegates when distributed.
- New env: `FSB_DB_BACKEND`, `FSB_PG_DSN`, `FSB_PG_POOL_SIZE`, `FSB_SCHEDULER_LEADER_TTL`, `FSB_EVENT_DEDUP_TTL`, `FSB_RATE_LIMIT_DISTRIBUTED`.
- 9 live-Postgres integration tests (skip when no local PG).

**Tests:** 328 passing (319 SQLite + 9 Postgres). ruff clean.

### 0.1.4

- Initial connector/skill/workflow registries, DAG engine, approval gates, scheduler, event bus, fusion-identity multi-tenant auth.
