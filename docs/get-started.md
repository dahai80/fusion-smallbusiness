---
doc_id: fusion-smallbusiness/get-started
product: fusion-smallbusiness
class: app
entry: service
doc_type: get-started
title: { zh: "fusion-smallbusiness 快速上手", en: "fusion-smallbusiness quick start" }
audience: engineer
status: draft
version: 0.2.1
updated: 2026-11-07
owner: "@dahai"
source_of_truth:
  - README.md
  - src/fsb/__main__.py
  - src/fsb/config.py
---

# 快速上手 / quick start

前置条件 / prerequisites: Python 3.12（fusion 共享 venv），可选上游：fusion-identity（认证）、fusion-gateway、fusion-cowork、fusion-rag、fusion-artifacts-engine。

## 1. 安装 / install

```bash
cd ~/fusion/fusion-smallbusiness
source ~/fusion/.venv/bin/activate
pip install -e ".[test]"
```

## 2. 启动 / start

```bash
fusion-smallbusiness
# 等价 / equivalent:
# uvicorn fsb.app:app --host 0.0.0.0 --port 11490
```

默认端口 11490（`FSB_SERVER_PORT`）；默认绑定 `0.0.0.0` 且认证开启（`FSB_AUTH_REQUIRE_JWT=true`），生产部署必须先完成第 3 步。
Default port is 11490 (`FSB_SERVER_PORT`); the default bind is `0.0.0.0` with auth enabled (`FSB_AUTH_REQUIRE_JWT=true`), so production deployments must complete step 3 first.

验证 / verify: 浏览器打开 `http://127.0.0.1:11490/docs` 查看 OpenAPI。
Verify by opening `http://127.0.0.1:11490/docs` (OpenAPI UI).

## 3. 生产配置 / production config

生产模式（默认 `FSB_STANDALONE_MODE=false`）要求：
Production mode (default `FSB_STANDALONE_MODE=false`) requires:

```bash
export FSB_FUSION_IDENTITY_URL=http://127.0.0.1:11470   # fusion-identity
export FSB_FUSION_IDENTITY_SERVICE_TOKEN=<token>        # service token
export FSB_SECRET_KEY=<strong random value>             # secret encryption-at-rest
```

未设置 `FSB_SECRET_KEY` 时连接器密钥明文落库（有日志告警）。
Without `FSB_SECRET_KEY`, connector secrets are stored in plaintext (a warning is logged).

## 4. 第一次调用 / first calls

请求需带 `X-Tenant-Id` 与 `Authorization: Bearer <JWT>`（fusion-identity 签发）：
Requests carry `X-Tenant-Id` and `Authorization: Bearer <JWT>` (issued by fusion-identity):

```bash
# 创建工作区
curl -s -X POST http://127.0.0.1:11490/api/v1/fsb/workspace \
  -H "X-Tenant-Id: t1" -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" -d '{"name":"demo"}'

# 创建工作流并运行
curl -s -X POST http://127.0.0.1:11490/api/v1/fsb/workflow \
  -H "X-Tenant-Id: t1" -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" -d @workflow.json
curl -s -X POST http://127.0.0.1:11490/api/v1/fsb/workflow/{wfId}/run \
  -H "X-Tenant-Id: t1" -H "Authorization: Bearer $JWT"
```

本地开发想先跳过认证：`FSB_STANDALONE_MODE=true`（集成路由返回 stub，勿对外暴露）。
For local development without auth: `FSB_STANDALONE_MODE=true` (integration routes return stubs; do not expose).

## 5. 测试 / tests

```bash
pytest tests/ -v
```

## 6. 停止 / stop

前台进程 `Ctrl-C` 即可；数据落 `FSB_DB_PATH`（默认 `fsb_data.db`）。
Stop the foreground process with `Ctrl-C`; data persists at `FSB_DB_PATH` (default `fsb_data.db`).

## 约束 / limits

- 限流：每租户令牌桶 60 容量 / 10 每秒，超限 429 + `Retry-After`；`/health` `/docs` `/openapi.json` `/redoc` 豁免。
  Rate limiting: per-tenant token bucket 60 / 10-per-second, 429 + `Retry-After` on overflow; `/health`, `/docs`, `/openapi.json`, `/redoc` are exempt.
- 运行历史默认保留 30 天（`FSB_RUN_RETENTION_DAYS`），小时级清理任务删除过期 run。
  Run history is retained for 30 days by default (`FSB_RUN_RETENTION_DAYS`); an hourly cleanup job deletes expired runs.
- 多副本部署需 Postgres 后端并设 `FSB_SCHEDULER_ENABLED=false`（leader-only 模式）。
  Multi-replica deployments need the Postgres backend and `FSB_SCHEDULER_ENABLED=false` (leader-only mode).

更多内容见 / see also: docs/api-reference.md, docs/config-reference.md, docs/troubleshooting.md
