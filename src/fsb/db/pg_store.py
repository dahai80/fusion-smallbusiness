import json
import logging

import asyncpg

logger = logging.getLogger(__name__)

MAX_PAGE = 200

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    ws_id TEXT PRIMARY KEY,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS connectors (
    conn_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS workflows (
    wf_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    wf_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_tasks (
    task_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    template_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS event_subscriptions (
    sub_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS webhooks (
    webhook_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connectors_ws ON connectors(ws_id);
CREATE INDEX IF NOT EXISTS idx_skills_ws ON skills(ws_id);
CREATE INDEX IF NOT EXISTS idx_workflows_ws ON workflows(ws_id);
CREATE INDEX IF NOT EXISTS idx_runs_ws ON runs(ws_id);
CREATE INDEX IF NOT EXISTS idx_runs_wf ON runs(wf_id);
CREATE INDEX IF NOT EXISTS idx_tasks_ws ON pending_tasks(ws_id);
CREATE INDEX IF NOT EXISTS idx_tasks_run ON pending_tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_events_ws ON events(ws_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_ws ON event_subscriptions(ws_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_ws ON webhooks(ws_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_title ON workspaces((data->>'title'));
CREATE INDEX IF NOT EXISTS idx_workspaces_project ON workspaces((data->>'projectId'));
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs((data->>'status'));
CREATE INDEX IF NOT EXISTS idx_tasks_status ON pending_tasks((data->>'status'));
CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON event_subscriptions((data->>'eventType'));
CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON event_subscriptions((data->>'enabled'));
CREATE INDEX IF NOT EXISTS idx_webhooks_enabled ON webhooks((data->>'enabled'));
CREATE TABLE IF NOT EXISTS run_traces (
    trace_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_traces_run ON run_traces(run_id);
CREATE TABLE IF NOT EXISTS scheduler_lease (
    holder TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS event_dedup (
    event_id TEXT PRIMARY KEY,
    ws_id TEXT NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_dedup_seen ON event_dedup(seen_at);
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    tenant_id TEXT PRIMARY KEY,
    tokens DOUBLE PRECISION NOT NULL,
    last_refill TIMESTAMPTZ NOT NULL
);
"""

# table -> (pk_col, ws_col)
_PK_MAP = {
    "workspaces": "ws_id",
    "connectors": "conn_id",
    "skills": "skill_id",
    "workflows": "wf_id",
    "runs": "run_id",
    "pending_tasks": "task_id",
    "templates": "template_id",
    "events": "event_id",
    "event_subscriptions": "sub_id",
    "webhooks": "webhook_id",
}
_WS_MAP = {
    "connectors": "ws_id",
    "skills": "ws_id",
    "workflows": "ws_id",
    "runs": "ws_id",
    "pending_tasks": "ws_id",
    "templates": "ws_id",
    "events": "ws_id",
    "event_subscriptions": "ws_id",
    "webhooks": "ws_id",
}


def _clamp_page(offset: int = 0, limit: int = 100) -> tuple[int, int]:
    offset = max(0, int(offset))
    limit = int(limit)
    if limit < 0:
        limit = MAX_PAGE
    limit = min(limit, MAX_PAGE)
    return offset, limit


def _load(raw) -> dict | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, (dict, list)):
            return raw
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("corrupt pg data blob skipped: %s", e)
        return None


class PostgresStore:
    def __init__(self, dsn: str, pool_size: int = 10):
        self.dsn = dsn
        self.pool_size = max(1, pool_size)
        self._pool: asyncpg.Pool | None = None

    async def init(self):
        self._pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=self.pool_size, command_timeout=30)
        async with self._pool.acquire() as conn:
            await conn.execute(_PG_SCHEMA)
        logger.info("pg store initialized (pool=%d)", self.pool_size)

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("pg store pool closed")

    async def is_healthy(self) -> bool:
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.warning("pg health check failed: %s", e)
            return False

    @staticmethod
    def _pk_col(table: str) -> str:
        return _PK_MAP.get(table, table.rstrip("s") + "_id")

    async def _get_one(self, table: str, pk: str, pk_col: str | None = None) -> dict | None:
        col = pk_col or self._pk_col(table)
        async with self._pool.acquire() as conn:
            raw = await conn.fetchval(f"SELECT data FROM {table} WHERE {col} = $1", pk)
        return _load(raw)

    async def _get_many(self, table: str, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        ws_col = _WS_MAP.get(table, "ws_id")
        offset, limit = _clamp_page(offset, limit)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT data FROM {table} WHERE {ws_col} = $1 LIMIT $2 OFFSET $3",
                ws_id,
                limit,
                offset,
            )
        return [d for d in (_load(r["data"]) for r in rows) if d is not None]

    async def _upsert(self, table: str, pk: str, data: dict, ws_id: str = "", extra_cols: dict | None = None):
        pk_col = self._pk_col(table)
        payload = json.dumps(data, default=str)
        is_root = table == "workspaces"
        async with self._pool.acquire() as conn:
            if is_root:
                await conn.execute(
                    f"INSERT INTO {table} ({pk_col}, data) VALUES ($1, $2::jsonb) "
                    f"ON CONFLICT({pk_col}) DO UPDATE SET data = EXCLUDED.data",
                    pk,
                    payload,
                )
            elif extra_cols:
                ws_col = _WS_MAP.get(table, "ws_id")
                cols = f"{pk_col}, {ws_col}, data, " + ", ".join(extra_cols)
                ph = "$1, $2, $3::jsonb, " + ", ".join(f"${i + 4}" for i in range(len(extra_cols)))
                updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in extra_cols)
                await conn.execute(
                    f"INSERT INTO {table} ({cols}) VALUES ({ph}) "
                    f"ON CONFLICT({pk_col}) DO UPDATE SET data = EXCLUDED.data, {updates}",
                    pk,
                    ws_id,
                    payload,
                    *extra_cols.values(),
                )
            else:
                ws_col = _WS_MAP.get(table, "ws_id")
                await conn.execute(
                    f"INSERT INTO {table} ({pk_col}, {ws_col}, data) VALUES ($1, $2, $3::jsonb) "
                    f"ON CONFLICT({pk_col}) DO UPDATE SET data = EXCLUDED.data",
                    pk,
                    ws_id,
                    payload,
                )

    async def _delete(self, table: str, pk: str, pk_col: str | None = None):
        col = pk_col or self._pk_col(table)
        async with self._pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {table} WHERE {col} = $1", pk)

    async def _delete_by_workspace(self, table: str, ws_id: str):
        ws_col = _WS_MAP.get(table, "ws_id")
        async with self._pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {table} WHERE {ws_col} = $1", ws_id)

    # workspace
    async def get_workspace(self, ws_id: str) -> dict | None:
        return await self._get_one("workspaces", ws_id, "ws_id")

    async def list_workspaces(
        self, offset: int = 0, limit: int = 100, search: str = "", project_id: str = ""
    ) -> list[dict]:
        offset, limit = _clamp_page(offset, limit)
        sql = "SELECT data FROM workspaces"
        conditions = []
        params: list = []
        idx = 1
        if search:
            conditions.append(f"data->>'title' ILIKE ${idx}")
            params.append(f"%{search}%")
            idx += 1
        if project_id:
            conditions.append(f"data->>'projectId' = ${idx}")
            params.append(project_id)
            idx += 1
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += f" LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [d for d in (_load(r["data"]) for r in rows) if d is not None]

    async def save_workspace(self, ws_id: str, data: dict):
        await self._upsert("workspaces", ws_id, data)

    async def delete_workspace(self, ws_id: str):
        child_tables = [
            "connectors",
            "skills",
            "workflows",
            "runs",
            "pending_tasks",
            "templates",
            "events",
            "event_subscriptions",
            "webhooks",
        ]
        async with self._pool.acquire() as conn, conn.transaction():
            for table in child_tables:
                ws_col = _WS_MAP.get(table, "ws_id")
                await conn.execute(f"DELETE FROM {table} WHERE {ws_col} = $1", ws_id)
            await conn.execute(
                "DELETE FROM run_traces WHERE run_id IN (SELECT run_id FROM runs WHERE ws_id = $1)",
                ws_id,
            )
            await conn.execute("DELETE FROM workspaces WHERE ws_id = $1", ws_id)
        logger.info("workspace deleted with cascade (atomic, pg): %s", ws_id)

    # connector
    async def get_connector(self, conn_id: str) -> dict | None:
        return await self._get_one("connectors", conn_id, "conn_id")

    async def list_connectors(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("connectors", ws_id, offset=offset, limit=limit)

    async def save_connector(self, conn_id: str, ws_id: str, data: dict):
        await self._upsert("connectors", conn_id, data, ws_id)

    async def delete_connector(self, conn_id: str):
        await self._delete("connectors", conn_id, "conn_id")

    # skill
    async def get_skill(self, skill_id: str) -> dict | None:
        return await self._get_one("skills", skill_id, "skill_id")

    async def list_skills(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("skills", ws_id, offset=offset, limit=limit)

    async def save_skill(self, skill_id: str, ws_id: str, data: dict):
        await self._upsert("skills", skill_id, data, ws_id)

    async def delete_skill(self, skill_id: str):
        await self._delete("skills", skill_id, "skill_id")

    # workflow
    async def get_workflow(self, wf_id: str) -> dict | None:
        return await self._get_one("workflows", wf_id, "wf_id")

    async def list_workflows(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("workflows", ws_id, offset=offset, limit=limit)

    async def save_workflow(self, wf_id: str, ws_id: str, data: dict):
        await self._upsert("workflows", wf_id, data, ws_id)

    async def delete_workflow(self, wf_id: str):
        await self._delete("workflows", wf_id, "wf_id")

    # run
    async def get_run(self, run_id: str) -> dict | None:
        data = await self._get_one("runs", run_id, "run_id")
        if data is not None:
            data["nodeTrace"] = await self.list_run_traces(run_id)
        return data

    async def list_runs(self, ws_id: str, wf_id: str | None = None, offset: int = 0, limit: int = 100) -> list[dict]:
        offset, limit = _clamp_page(offset, limit)
        async with self._pool.acquire() as conn:
            if wf_id:
                rows = await conn.fetch(
                    "SELECT data FROM runs WHERE ws_id = $1 AND wf_id = $2 LIMIT $3 OFFSET $4",
                    ws_id,
                    wf_id,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    "SELECT data FROM runs WHERE ws_id = $1 LIMIT $2 OFFSET $3",
                    ws_id,
                    limit,
                    offset,
                )
        runs = [d for d in (_load(r["data"]) for r in rows) if d is not None]
        if runs:
            run_ids = [r.get("runId", "") for r in runs]
            traces_by_run = await self._batch_traces(run_ids)
            for r in runs:
                r["nodeTrace"] = traces_by_run.get(r.get("runId", ""), [])
        return runs

    async def _batch_traces(self, run_ids: list[str]) -> dict[str, list[dict]]:
        if not run_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT run_id, data FROM run_traces WHERE run_id = ANY($1) ORDER BY run_id, seq ASC",
                run_ids,
            )
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            parsed = _load(row["data"])
            if parsed is not None:
                grouped.setdefault(row["run_id"], []).append(parsed)
        return grouped

    async def save_run(self, run_id: str, ws_id: str, wf_id: str, data: dict):
        persist = dict(data)
        persist["nodeTrace"] = []
        await self._upsert("runs", run_id, persist, ws_id, {"wf_id": wf_id})

    async def append_run_trace(self, run_id: str, seq: int, trace: dict):
        trace_id = f"{run_id}_{seq}"
        payload = json.dumps(trace, default=str)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO run_traces (trace_id, run_id, node_id, seq, data) "
                "VALUES ($1, $2, $3, $4, $5::jsonb) "
                "ON CONFLICT(trace_id) DO UPDATE SET data = EXCLUDED.data, "
                "node_id = EXCLUDED.node_id, seq = EXCLUDED.seq",
                trace_id,
                run_id,
                trace.get("nodeId", ""),
                seq,
                payload,
            )

    async def list_run_traces(self, run_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT data FROM run_traces WHERE run_id = $1 ORDER BY seq ASC", run_id)
        return [d for d in (_load(r["data"]) for r in rows) if d is not None]

    async def delete_run_traces(self, run_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM run_traces WHERE run_id = $1", run_id)

    async def cas_run_status(self, run_id: str, ws_id: str, wf_id: str, data: dict, expected_status: str) -> bool:
        payload = json.dumps(data, default=str)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE runs SET data = $1::jsonb WHERE run_id = $2 AND data->>'status' = $3",
                payload,
                run_id,
                expected_status,
            )
        updated = result.endswith(" 1")
        if not updated:
            logger.warning("cas_run_status(pg): no row updated run=%s expected_status=%s", run_id, expected_status)
        return updated

    # pending task
    async def get_task(self, task_id: str) -> dict | None:
        return await self._get_one("pending_tasks", task_id, "task_id")

    async def list_pending_tasks(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        offset, limit = _clamp_page(offset, limit)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM pending_tasks WHERE ws_id = $1 AND data->>'status' = 'pending' LIMIT $2 OFFSET $3",
                ws_id,
                limit,
                offset,
            )
        return [d for d in (_load(r["data"]) for r in rows) if d is not None]

    async def save_task(self, task_id: str, ws_id: str, run_id: str, data: dict):
        await self._upsert("pending_tasks", task_id, data, ws_id, {"run_id": run_id})

    async def delete_task(self, task_id: str):
        await self._delete("pending_tasks", task_id, "task_id")

    # template
    async def get_template(self, tpl_id: str) -> dict | None:
        return await self._get_one("templates", tpl_id, "template_id")

    async def list_templates(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("templates", ws_id, offset=offset, limit=limit)

    async def save_template(self, tpl_id: str, ws_id: str, data: dict):
        await self._upsert("templates", tpl_id, data, ws_id)

    async def delete_template(self, tpl_id: str):
        await self._delete("templates", tpl_id, "template_id")

    # event
    async def get_event(self, event_id: str) -> dict | None:
        return await self._get_one("events", event_id, "event_id")

    async def list_events(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("events", ws_id, offset=offset, limit=limit)

    async def save_event(self, event_id: str, ws_id: str, data: dict):
        await self._upsert("events", event_id, data, ws_id)

    async def delete_event(self, event_id: str):
        await self._delete("events", event_id, "event_id")

    # event subscription
    async def get_subscription(self, sub_id: str) -> dict | None:
        return await self._get_one("event_subscriptions", sub_id, "sub_id")

    async def list_subscriptions(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("event_subscriptions", ws_id, offset=offset, limit=limit)

    async def save_subscription(self, sub_id: str, ws_id: str, data: dict):
        await self._upsert("event_subscriptions", sub_id, data, ws_id)

    async def delete_subscription(self, sub_id: str):
        await self._delete("event_subscriptions", sub_id, "sub_id")

    async def find_matching_subscriptions(self, event_type: str, source: str = "", ws_id: str = "") -> list[dict]:
        async with self._pool.acquire() as conn:
            if ws_id:
                rows = await conn.fetch(
                    "SELECT data FROM event_subscriptions WHERE ws_id = $1 "
                    "AND data->>'eventType' = $2 AND (data->>'enabled')::boolean = true",
                    ws_id,
                    event_type,
                )
            else:
                rows = await conn.fetch(
                    "SELECT data FROM event_subscriptions "
                    "WHERE data->>'eventType' = $1 AND (data->>'enabled')::boolean = true",
                    event_type,
                )
        results = [d for d in (_load(r["data"]) for r in rows) if d is not None]
        if source:
            results = [r for r in results if r.get("source") is None or r.get("source") == source]
        logger.info(
            "found %d matching subscriptions (pg) for event_type=%s source=%s ws=%s",
            len(results),
            event_type,
            source,
            ws_id,
        )
        return results

    # webhook
    async def get_webhook(self, webhook_id: str) -> dict | None:
        return await self._get_one("webhooks", webhook_id, "webhook_id")

    async def list_webhooks(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("webhooks", ws_id, offset=offset, limit=limit)

    async def save_webhook(self, webhook_id: str, ws_id: str, data: dict):
        await self._upsert("webhooks", webhook_id, data, ws_id)

    async def delete_webhook(self, webhook_id: str):
        await self._delete("webhooks", webhook_id, "webhook_id")

    async def find_webhooks_for_event(self, ws_id: str, event: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM webhooks WHERE ws_id = $1 AND (data->>'enabled')::boolean = true",
                ws_id,
            )
        results = [d for d in (_load(r["data"]) for r in rows) if d is not None]
        results = [r for r in results if event in r.get("events", [])]
        logger.info("found %d webhooks (pg) for ws=%s event=%s", len(results), ws_id, event)
        return results

    async def cleanup_old_runs(self, retention_days: int = 30, keep_per_ws: int = 200) -> dict:
        from datetime import UTC, datetime, timedelta

        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        deleted = {"runs": 0, "pending_tasks": 0, "events": 0}
        async with self._pool.acquire() as conn, conn.transaction():
            del_traces = await conn.execute(
                "DELETE FROM run_traces WHERE run_id IN ("
                "  SELECT run_id FROM runs WHERE data->>'endTime' IS NOT NULL "
                "  AND data->>'endTime' != 'null' AND data->>'endTime' < $1)",
                cutoff,
            )
            logger.info("pg retention: deleted %s trace rows", del_traces)
            r = await conn.execute(
                "DELETE FROM runs WHERE data->>'endTime' IS NOT NULL "
                "AND data->>'endTime' != 'null' AND data->>'endTime' < $1",
                cutoff,
            )
            deleted["runs"] = _rows_from_result(r)
            r = await conn.execute("DELETE FROM pending_tasks WHERE data->>'status' IN ('approved','denied')")
            deleted["pending_tasks"] = _rows_from_result(r)
            r = await conn.execute(
                "DELETE FROM events WHERE event_id NOT IN ("
                "  SELECT event_id FROM events ORDER BY event_id DESC LIMIT $1)",
                keep_per_ws * 10,
            )
            deleted["events"] = _rows_from_result(r)
        logger.info("pg retention cleanup: %s", deleted)
        return deleted

    # ---- distributed primitives ----

    async def try_acquire_leader(self, holder: str, ttl_seconds: int) -> bool:
        from datetime import UTC, datetime, timedelta

        expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT expires_at FROM scheduler_lease WHERE holder = $1", holder)
            if existing:
                await conn.execute("UPDATE scheduler_lease SET expires_at = $1 WHERE holder = $2", expires, holder)
                return True
            result = await conn.execute(
                "INSERT INTO scheduler_lease (holder, expires_at) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                holder,
                expires,
            )
            return result.endswith(" 1")

    async def renew_leader(self, holder: str, ttl_seconds: int) -> bool:
        from datetime import UTC, datetime, timedelta

        expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        async with self._pool.acquire() as conn:
            result = await conn.execute("UPDATE scheduler_lease SET expires_at = $1 WHERE holder = $2", expires, holder)
            return result.endswith(" 1")

    async def is_leader(self, holder: str) -> bool:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT expires_at FROM scheduler_lease WHERE holder = $1", holder)
        return row is not None and row["expires_at"] > now

    async def release_leader(self, holder: str):
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM scheduler_lease WHERE holder = $1", holder)

    async def event_seen(self, event_id: str, ws_id: str, ttl_seconds: int) -> bool:
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            existing = await conn.fetchval("SELECT seen_at FROM event_dedup WHERE event_id = $1", event_id)
            if existing is not None:
                await conn.execute("UPDATE event_dedup SET seen_at = $1 WHERE event_id = $2", now, event_id)
                return True
            cutoff = now - timedelta(seconds=ttl_seconds)
            await conn.execute(
                "INSERT INTO event_dedup (event_id, ws_id, seen_at) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                event_id,
                ws_id,
                now,
            )
            await conn.execute("DELETE FROM event_dedup WHERE seen_at < $1", cutoff)
            return False

    async def rate_limit_consume(self, tenant_id: str, capacity: int, refill_rate: int) -> bool:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT tokens, last_refill FROM rate_limit_buckets WHERE tenant_id = $1",
                tenant_id,
            )
            if row is None:
                tokens = float(capacity)
                await conn.execute(
                    "INSERT INTO rate_limit_buckets (tenant_id, tokens, last_refill) VALUES ($1, $2, $3) "
                    "ON CONFLICT DO NOTHING",
                    tenant_id,
                    tokens,
                    now,
                )
            else:
                elapsed = (now - row["last_refill"]).total_seconds()
                tokens = min(float(capacity), float(row["tokens"]) + elapsed * refill_rate)
            if tokens < 1.0:
                await conn.execute(
                    "UPDATE rate_limit_buckets SET tokens = $1, last_refill = $2 WHERE tenant_id = $3",
                    tokens,
                    now,
                    tenant_id,
                )
                return False
            tokens -= 1.0
            await conn.execute(
                "UPDATE rate_limit_buckets SET tokens = $1, last_refill = $2 WHERE tenant_id = $3",
                tokens,
                now,
                tenant_id,
            )
            return True


def _rows_from_result(result: str) -> int:
    if not result:
        return 0
    parts = result.split()
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0
