---
doc_id: fusion-smallbusiness/product-page
product: fusion-smallbusiness
class: app
entry: service
doc_type: product-page
title: { zh: "fusion-smallbusiness 产品页", en: "fusion-smallbusiness product page" }
audience: engineer
status: draft
version: 0.2.1
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - README.md
  - src/fsb/app.py
  - src/fsb/config.py
---

# fusion-smallbusiness 产品页 / product page

## 一句话定位 / positioning

面向小微团队的跨 SaaS 智能业务工作区服务：连接器（数据接入）→ 技能（原子能力）→ 工作流（业务流水线）三层架构，内置 LangGraph 风格 DAG 引擎与 7 类节点，经 REST API（`/api/v1/fsb`）对外提供能力。
Cross-SaaS intelligent business workspace service for small teams: a three-layer architecture (connectors -> skills -> workflows) with a LangGraph-style DAG engine and 7 node types, served over the REST API at `/api/v1/fsb`.

## 它替用户免掉了什么 / what users no longer have to do

- 不再为每个 SaaS 手写对接代码：连接器生命周期（创建/OAuth2 授权/刷新/断开）由服务托管。
  No more hand-written SaaS glue: the connector lifecycle (create / OAuth2 authorize / refresh / disconnect) is managed by the service.
- 不再为写操作自建审批流：`APPROVAL_GATE_NODE` 强制人工审批，待办任务经 `/task/*` 审批/拒绝/编辑。
  No self-built approval flows for write operations: `APPROVAL_GATE_NODE` enforces human approval; pending tasks are approved/denied/edited via `/task/*`.
- 不再手工归档工作流产出：`OUTPUT_NODE` 自动生成 Artifact 并同步到知识库。
  No manual archiving of workflow output: `OUTPUT_NODE` auto-creates artifacts and syncs to the knowledge base.
- 不再自建多租户认证：工作区路由绑定 fusion-identity JWT 与 `X-Tenant-Id`，跨租户访问返回 403。
  No bespoke multi-tenant auth: workspace routes bind fusion-identity JWTs to `X-Tenant-Id`; cross-tenant access returns 403.

## 约束与边界 / constraints and limits

- 单节点默认 SQLite（WAL）；多节点部署须切 `FSB_DB_BACKEND=postgres` 并配 `FSB_PG_DSN`，调度走 leader lease。
  Single-node defaults to SQLite (WAL); multi-node requires `FSB_DB_BACKEND=postgres` with `FSB_PG_DSN`, with scheduler leader leasing.
- `FSB_STANDALONE_MODE=true` 跳过认证与限流中间件、集成路由返回 stub——仅限开发/测试，不得公开暴露。
  `FSB_STANDALONE_MODE=true` skips auth and rate-limit middleware and stubs integration routes — dev/test only, never expose publicly.
- 请求体上限 2 MiB（`FSB_MAX_BODY_BYTES`），超限 413；每租户令牌桶限流（默认 60 容量 / 10 每秒回填）。
  Request bodies are capped at 2 MiB (`FSB_MAX_BODY_BYTES`, 413 on overflow); per-tenant token-bucket rate limiting (60 capacity / 10 per second refill by default).
- 上游 fusion 服务不可用时客户端优雅降级，不阻塞工作流执行；但对应能力（LLM 技能、连接器调用）不可用。
  Upstream fusion services degrade gracefully and never block workflow execution, but the dependent capabilities (LLM skills, connector calls) are unavailable.

## 入口 / entry points

| 入口 / entry | 说明 / description |
|---|---|
| REST API | `http://<host>:11490/api/v1/fsb/...`（OpenAPI 于 `/docs`） |
| CLI | `fusion-smallbusiness`（启动服务；端口 `FSB_SERVER_PORT`，默认 11490） |
| 前端 | Workflow Canvas 为外部宿主（fusion-web-shell / fusion-studio），本仓库只提供服务端 |

## 用户与场景 / audience and scenarios

- 平台工程师：把 FSB 作为订阅内的业务模块部署，配置 fusion-identity / gateway / cowork 上游。
  Platform engineers: deploy FSB as a subscription business module and wire the fusion-identity / gateway / cowork upstreams.
- 集成开发者：经 REST API 创建工作流、注册 webhook、消费事件订阅。
  Integration developers: build workflows, register webhooks and consume event subscriptions over the REST API.
