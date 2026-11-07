---
doc_id: fusion-smallbusiness/api-reference
product: fusion-smallbusiness
class: app
entry: service
doc_type: api-reference
title: { zh: "fusion-smallbusiness REST API 参考", en: "fusion-smallbusiness REST API reference" }
audience: engineer
status: draft
version: 0.2.1
updated: 2026-11-07
owner: "@dahai"
source_of_truth:
  - src/fsb/app.py
  - src/fsb/routes
---

# REST API 参考 / REST API reference

Base URL: `http://<host>:11490/api/v1/fsb`。OpenAPI: `/docs`、`/openapi.json`。

## 认证 / auth

- 非独立模式下，除 `/health` `/docs` `/openapi.json` `/redoc` 外的所有请求需 `X-Tenant-Id` 头 + `Authorization: Bearer <JWT>`；JWT 经 fusion-identity `POST /api/v1/auth/verify` 校验，`tid` 必须与 `X-Tenant-Id` 一致，否则 401/403。
  In non-standalone mode every request except `/health`, `/docs`, `/openapi.json`, `/redoc` needs the `X-Tenant-Id` header plus `Authorization: Bearer <JWT>`; the JWT is verified against fusion-identity `POST /api/v1/auth/verify`, the `tid` claim must match `X-Tenant-Id`, else 401/403.
- `FSB_STANDALONE_MODE=true` 时认证与限流中间件跳过（仅开发/测试）。
  With `FSB_STANDALONE_MODE=true` the auth and rate-limit middleware are skipped (dev/test only).
- 错误响应为 `{ detail: ... }` 形态；限流 429 + `Retry-After`；体超限 413。
  Error responses use the `{ detail: ... }` shape; rate limiting is 429 + `Retry-After`; oversized bodies are 413.

## 路由组 / route groups

| 前缀 / prefix | 能力 / capability |
|---|---|
| `/workspace` | 工作区 CRUD、`/{wfId}/canvas-layout` 画布布局（拒绝 NaN/Infinity 与未知节点）、租户绑定 |
| `/connector` | 连接器生命周期：创建、`/{connId}/oauth2/authorize|callback`、`/refresh`、`/disconnect`、删除 |
| `/connector-meta` | 连接器元数据（可用 SaaS 目录） |
| `/skill` | 技能 CRUD、`/{skillId}/test` 技能试跑 |
| `/workflow` | 工作流 CRUD、`/import`、`/{wfId}/export`、`/{wfId}/run`、`/{wfId}/schedule` 调度 |
| `/intent` | 意图匹配 `/match`、命令列表 `/commands` |
| `/execution` | `/run` 执行、`/history`、`/{runId}` 详情、`/export` |
| `/task`（integration） | 审批门待办：`/task/pending`、`/{taskId}/approve|deny|edit` |
| `/external` | `/webhook/register`、`/webhook`、`/event`、`/event/subscription` 事件订阅、`/workflow/{wfId}/trigger` |
| `/variable` | 变量与模板 CRUD |
| `/chat` | `/chat/run` 对话、`/agent/bind`/`/agent/unbind` agent 绑定 |
| `/sync-to-project` 等集成路由 | 产出同步 / Artifact 创建 / 知识库归档 / 快照导入（独立模式下返回 stub） |

路径以 `/docs` 的 OpenAPI schema 为准；本页不逐一复制参数。
The OpenAPI schema at `/docs` is authoritative for paths and parameters; this page does not duplicate them.

## 多租户语义 / multi-tenant semantics

- 工作区创建/导入时绑定租户；列表按租户过滤；跨租户访问 403。
  Workspaces are bound to the tenant at create/import; lists are tenant-scoped; cross-tenant access is 403.
- EventBus：带 `workspaceId` 的事件只匹配该工作区的订阅；无 `workspaceId` 的事件只存储不广播。
  EventBus: events carrying a `workspaceId` match only that workspace's subscriptions; events without one are stored but never broadcast.
- 事件去重窗口 60 秒，单事件类型深度上限 5，防递归触发。
  A 60s dedup window and a per-event-type depth cap of 5 prevent recursive trigger loops.

## 约束 / constraints

- 列表查询参数钳制到 200 行页上限（负值拒绝）。
  List query params are clamped to a 200-row page ceiling (negatives rejected).
- Webhook 与 `api_call` 技能 URL 经 SSRF 守卫（仅 http/https，拒绝回环/私网/链路本地/保留地址），并固定已解析 IP 防 DNS 重绑定。
  Webhook and `api_call` skill URLs pass an SSRF guard (http/https only; loopback/private/link-local/reserved hosts rejected) with resolved-IP pinning against DNS rebinding.
- 密钥加密落库（`fsbenc1:` 前缀信封加密），API 响应中密钥一律脱敏。
  Secrets are stored encrypted (envelope scheme, `fsbenc1:` prefix) and redacted from all API responses.
