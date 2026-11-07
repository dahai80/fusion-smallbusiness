---
doc_id: fusion-smallbusiness/config-reference
product: fusion-smallbusiness
class: app
entry: service
doc_type: config-reference
title: { zh: "fusion-smallbusiness 配置参考", en: "fusion-smallbusiness config reference" }
audience: engineer
status: draft
version: 0.2.1
updated: 2026-11-07
owner: "@dahai"
source_of_truth:
  - src/fsb/config.py
  - README.md
---

# 配置参考 / config reference

全部配置经环境变量（`src/fsb/config.py`），无配置文件。
All configuration is via environment variables (`src/fsb/config.py`); there is no config file.

## 服务与存储 / server and storage

| 变量 / variable | 默认值 / default | 说明 / description |
|---|---|---|
| `FSB_SERVER_HOST` | `0.0.0.0` | 绑定地址；生产建议置于反代之后 |
| `FSB_SERVER_PORT` | `11490` | 服务端口（port-registry 登记 fusion-smallbusiness） |
| `FSB_DB_BACKEND` | `sqlite` | `sqlite`（单机）或 `postgres`（多节点） |
| `FSB_DB_PATH` | `fsb_data.db` | SQLite 文件路径（生产用绝对路径） |
| `FSB_DB_POOL_SIZE` | `8` | aiosqlite 连接池（`:memory:` 强制 1；WAL + busy_timeout 5000） |
| `FSB_PG_DSN` | 空 | Postgres DSN，`FSB_DB_BACKEND=postgres` 时必填 |
| `FSB_PG_POOL_SIZE` | `10` | asyncpg 连接池 |

## 认证与安全 / auth and security

| 变量 / variable | 默认值 / default | 说明 / description |
|---|---|---|
| `FSB_STANDALONE_MODE` | `false` | `true` 跳过认证/限流且集成路由返回 stub；仅开发测试，不得公开暴露 |
| `FSB_FUSION_IDENTITY_URL` | `http://127.0.0.1:11470` | fusion-identity 服务地址（JWT 校验） |
| `FSB_FUSION_IDENTITY_SERVICE_TOKEN` | 空 | `POST /api/v1/auth/verify` 的服务令牌 |
| `FSB_AUTH_REQUIRE_JWT` | `true` | 非独立模式强制 JWT |
| `FSB_SECRET_KEY` | 空 | 静态加密主密钥（scrypt + HMAC 信封，`fsbenc1:` 前缀）；为空时明文落库并告警 |
| `FSB_RATE_LIMIT_CAPACITY` | `60` | 每租户令牌桶容量 |
| `FSB_RATE_LIMIT_REFILL` | `10` | 每秒回填速率 |
| `FSB_RATE_LIMIT_DISTRIBUTED` | `false` | `true` 时限流走 `rate_limit_buckets` 表（跨节点共享） |
| `FSB_MAX_BODY_BYTES` | `2097152` | POST/PUT/PATCH 体上限，超限 413 |

## 上游 fusion 服务 / upstream fusion services

| 变量 / variable | 默认值 / default | 用途 / purpose |
|---|---|---|
| `FSB_FUSION_MLX_URL` | `http://localhost:11432` | LLM（经 fusion-gateway） |
| `FSB_FUSION_GATEWAY_URL` | `http://localhost:11444` | SaaS 连接器 Action 调用 |
| `FSB_FUSION_COWORK_URL` | `http://localhost:11437` | 审批门通知 / 项目同步 |
| `FSB_FUSION_CHAT_URL` | `http://127.0.0.1:11460` | agent 绑定 + run 完成回调 |
| `FSB_FUSION_RAG_URL` | `http://127.0.0.1:11436` | 知识库归档 |
| `FSB_FUSION_RAG_API_KEY` | 空 | fusion-rag 鉴权（可选） |
| `FSB_ARTIFACTS_ENGINE_URL` | `http://127.0.0.1:11451` | Artifact 生成 |

## 调度与运行时 / scheduler and runtime

| 变量 / variable | 默认值 / default | 说明 / description |
|---|---|---|
| `FSB_SCHEDULER_ENABLED` | `true` | 进程内 APScheduler cron 派发；多副本 leader-only 模式设 `false` |
| `FSB_SCHEDULER_LEADER_TTL` | `30` | leader 租约 TTL（秒），`scheduler_lease` 表背书 |
| `FSB_EVENT_DEDUP_TTL` | `120` | EventBus 分布式去重窗口（秒） |
| `FSB_RUN_RETENTION_DAYS` | `30` | run 历史保留天数（小时级清理） |
| `FSB_LLM_DEFAULT_MODEL` | `default` | 默认模型名 |
| `FSB_EMBEDDING_MODEL` | `BGE-M3` | 默认 embedding 模型 |
| `FSB_HTTP_TIMEOUT` | `10` | 上游 HTTP 超时（秒） |

## 约束 / constraints

- 无热加载：改环境变量后需重启进程。
  No hot reload: restart the process after changing variables.
- 上游客户端全部优雅降级（连接失败不阻塞工作流），但对应能力不可用。
  All upstream clients degrade gracefully (connection failures never block workflows), but the dependent capabilities are unavailable.
- SQLite 模式不支持多节点共享存储；多节点必须 Postgres。
  SQLite mode does not support shared multi-node storage; Postgres is required there.
