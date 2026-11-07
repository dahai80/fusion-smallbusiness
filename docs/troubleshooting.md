---
doc_id: fusion-smallbusiness/troubleshooting
product: fusion-smallbusiness
class: app
entry: service
doc_type: troubleshooting
title: { zh: "fusion-smallbusiness 故障排查", en: "fusion-smallbusiness troubleshooting" }
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

# 故障排查 / troubleshooting

## 症状速查 / symptom index

| 症状 / symptom | 处理 / fix |
|---|---|
| 所有请求 401 | 未带 `X-Tenant-Id` + Bearer JWT，或 JWT 校验失败；确认 fusion-identity 可达且 `FSB_FUSION_IDENTITY_SERVICE_TOKEN` 已配置 |
| 403 访问他人工作区 | 路径 `{wsId}` 绑定到 JWT `tid` 对应租户，属预期行为 |
| 429 Too Many Requests | 每租户令牌桶溢出；按 `Retry-After` 重试或调 `FSB_RATE_LIMIT_CAPACITY`/`FSB_RATE_LIMIT_REFILL` |
| 413 Payload Too Large | 请求体超过 2 MiB（`FSB_MAX_BODY_BYTES`） |
| 集成路由返回 stub | `FSB_STANDALONE_MODE=true` 的预期行为；生产切回 `false` 并配置 identity |
| 技能节点不产出 LLM 结果 | `FSB_FUSION_MLX_URL` 上游不可用；客户端优雅降级不阻塞流程，恢复上游后重跑 |
| 连接器 OAuth2 回调失败 | 确认 `FSB_FUSION_GATEWAY_URL` 可达、连接器未断开；重走 `/connector/{connId}/oauth2/authorize` |
| 多副本下 cron 重复/不触发 | 检查 `FSB_DB_BACKEND=postgres` 与 `scheduler_lease` 表；非 leader 副本设 `FSB_SCHEDULER_ENABLED=false` |
| 事件不触发工作流 | 事件需带 `workspaceId` 且有匹配订阅；去重窗口 60 秒、类型深度上限 5 会拦截风暴 |
| SQLite 锁告警 | WAL 已默认开启（busy_timeout 5000）；高并发或多节点场景切 Postgres |

## 诊断步骤 / diagnosis steps

1. `curl http://127.0.0.1:11490/health` — 进程存活与基本依赖。
   Liveness and basic dependency check.
2. `/docs` — 确认路由与 schema 版本。
   Confirm routes and schema via the OpenAPI UI.
3. 本地复现生产认证：保持 `FSB_STANDALONE_MODE=false`，用真实 JWT 打一个只读端点。
   Reproduce production auth locally: keep `FSB_STANDALONE_MODE=false` and hit a read-only endpoint with a real JWT.
4. 测试基线：`pytest tests/ -v`（README 记录 307 tests / 95% coverage）。
   Test baseline: `pytest tests/ -v` (README records 307 tests / 95% coverage).
5. 检查 run 历史：`GET /api/v1/fsb/execution/history` 定位失败 run 与错误节点。
   Inspect `GET /api/v1/fsb/execution/history` to locate failed runs and the failing node.

## 数据与迁移 / data and migration

- SQLite：`FSB_DB_PATH` 指向的文件即全部状态（10 域表 + `run_traces` + 分布式原语表）；备份直接停机拷贝。
  SQLite: the file at `FSB_DB_PATH` holds all state (10 domain tables plus `run_traces` and the distributed-primitive tables); back up by copying while stopped.
- Postgres：10 域表带 JSONB 列与表达式索引。
  Postgres: domain tables use JSONB columns and expression indexes.
- Schema 版本由 `PRAGMA user_version` 管理，启动时前向自动迁移（仅新增索引类变更），无手工迁移步骤。
  Schema version is tracked via `PRAGMA user_version` with a forward-only migration registry applied at startup (index-only changes); no manual migration step.
- run 历史默认 30 天清理（`FSB_RUN_RETENTION_DAYS`），需要更长保留请调大或导出（`/execution/export`）。
  Run history is cleaned after 30 days by default (`FSB_RUN_RETENTION_DAYS`); increase it or export via `/execution/export`.

## 常见误区 / common pitfalls

- `FSB_STANDALONE_MODE=true` 不是"演示模式"，它关闭认证与限流，绝不能暴露公网。
  `FSB_STANDALONE_MODE=true` is not a demo switch: it disables auth and rate limiting and must never face the public internet.
- `FSB_SECRET_KEY` 换钥后旧密文无法解密：返回空值并记日志（不抛异常），连接器需重新授权。
  Rotating `FSB_SECRET_KEY` makes old ciphertext undecryptable: it returns empty values with a log line (no exception) and connectors must be re-authorized.
- 默认绑定 `0.0.0.0`：务必置于反代/防火墙后，或改 `FSB_SERVER_HOST=127.0.0.1` 仅本机使用。
  The default bind is `0.0.0.0`: put the service behind a reverse proxy/firewall, or set `FSB_SERVER_HOST=127.0.0.1` for local-only use.
