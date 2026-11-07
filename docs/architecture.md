---
doc_id: fusion-smallbusiness/architecture
product: fusion-smallbusiness
class: app
entry: service
doc_type: architecture
title: { zh: "fusion-smallbusiness 架构", en: "fusion-smallbusiness architecture" }
audience: engineer
status: draft
version: 0.2.1
updated: 2026-11-07
owner: "@dahai"
source_of_truth:
  - README.md
  - src/fsb/app.py
---

# 架构 / architecture

## 三层模型 / three-layer model

```
Connectors (数据接入) → Skills (原子能力) → Workflows (业务流水线)
```

7 类节点：`START_NODE` / `END_NODE`（边界）、`CONNECTOR_NODE`（SaaS 调用）、`SKILL_NODE`（LLM/函数技能）、`CONDITION_NODE`（分支）、`APPROVAL_GATE_NODE`（人工审批，写操作必需）、`OUTPUT_NODE`（产出生成与归档）。
7 node types: `START_NODE` / `END_NODE` (boundaries), `CONNECTOR_NODE` (SaaS invocation), `SKILL_NODE` (LLM/function skills), `CONDITION_NODE` (branching), `APPROVAL_GATE_NODE` (human approval, required for write operations), `OUTPUT_NODE` (output generation and archiving).

## 模块布局 / module layout

```
src/fsb/
├── app.py          # FastAPI 应用 + 生命周期 + 中间件装配
├── config.py       # 全部环境变量集中解析
├── auth.py         # fusion-identity JWT 中间件
├── middleware.py   # 限流(令牌桶) + 体长限制
├── tenant_dep.py   # 租户绑定依赖
├── routes/         # 11 个路由模块（workspace/connector/skill/workflow/execution/...）
├── engine/         # DAG 执行引擎 + secret_crypto + url_guard
├── services/       # 上游客户端（llm/gateway/cowork/rag/artifact/chat），全部优雅降级
├── db/store.py     # SQLite/Postgres 双后端存储（10 域表）
└── models/         # Pydantic 模型
```

## 请求链 / request chain

```
client ──▶ rate-limit + body-size middleware (非独立模式)
       ──▶ auth middleware (fusion-identity JWT + X-Tenant-Id, tid 必须一致)
       ──▶ router /api/v1/fsb/* ──▶ engine 执行 DAG
engine ──▶ services/* ──▶ fusion-mlx / gateway / cowork / rag / artifacts-engine
```

## 关键决策 / key decisions

- **双存储后端**：SQLite（单机 WAL）与 Postgres（JSONB + 表达式索引）同一套域表语义；多节点原语（scheduler lease、事件去重、分布式限流桶）落在表上，切后端不改业务代码。
  Dual storage backends: SQLite (single-node WAL) and Postgres (JSONB plus expression indexes) share one domain-table semantic; multi-node primitives (scheduler lease, event dedup, distributed rate-limit buckets) live in tables, so switching backends needs no business-code change.
- **审批门前置**：写操作必须经 `APPROVAL_GATE_NODE`，待办由 integration 路由 `/task/*` 处理，通知推送 cowork。
  Approval-first: write operations must pass `APPROVAL_GATE_NODE`; pending tasks are handled by the integration routes `/task/*` with notifications pushed to cowork.
- **静态加密内建**：`engine/secret_crypto` 用纯标准库信封加密（scrypt + HMAC-SHA256 keystream + encrypt-then-MAC），密钥仅在使用点解密、响应中一律脱敏。
  Built-in encryption at rest: `engine/secret_crypto` provides a stdlib-only envelope scheme (scrypt + HMAC-SHA256 keystream + encrypt-then-MAC); secrets decrypt only at use sites and are redacted from responses.
- **SSRF 守卫 + IP 固定**：`engine/url_guard` 在技能执行与 webhook 派发两路径校验 URL 并固定解析 IP，封死 DNS 重绑定窗口。
  SSRF guard with IP pinning: `engine/url_guard` validates URLs on both the skill-execution and webhook-dispatch paths and pins the resolved IP, closing the DNS-rebinding window.
- **fail-visible 数据可用性**：上游客户端优雅降级但事件/审批/产出能力记录缺失，不伪造成功。
  Fail-visible data availability: upstream clients degrade gracefully while missing event/approval/output capabilities are recorded, never faked as success.

## 边界与限制 / boundaries and limits

- 本仓库只提供服务端；Workflow Canvas 前端由 fusion-web-shell / fusion-studio 宿主。
  This repo ships the service only; the Workflow Canvas frontend is hosted by fusion-web-shell / fusion-studio.
- 认证完全依赖 fusion-identity，本仓库不签发令牌。
  Authentication relies entirely on fusion-identity; this repo issues no tokens.
- 单事件类型深度上限 5、60 秒去重窗口，递归触发会被截断。
  A per-event-type depth cap of 5 and a 60s dedup window truncate recursive triggering.
