import asyncio
import json
import logging
import os
from datetime import UTC
from typing import ClassVar

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("FSB_DB_PATH", "fsb_data.db")
MAX_PAGE = 200
_POOL_SIZE = max(1, int(os.environ.get("FSB_DB_POOL_SIZE", "8")))


def _resolve_pool_size(db_path: str) -> int:
    if db_path == ":memory:":
        return 1
    return _POOL_SIZE


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    wsId TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connectors (
    connId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skills (
    skillId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflows (
    wfId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    runId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    wfId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_tasks (
    taskId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    runId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    templateId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    eventId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_subscriptions (
    subId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhooks (
    webhookId TEXT PRIMARY KEY,
    wsId TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connectors_ws ON connectors(wsId);
CREATE INDEX IF NOT EXISTS idx_skills_ws ON skills(wsId);
CREATE INDEX IF NOT EXISTS idx_workflows_ws ON workflows(wsId);
CREATE INDEX IF NOT EXISTS idx_runs_ws ON runs(wsId);
CREATE INDEX IF NOT EXISTS idx_runs_wf ON runs(wfId);
CREATE INDEX IF NOT EXISTS idx_tasks_ws ON pending_tasks(wsId);
CREATE INDEX IF NOT EXISTS idx_tasks_run ON pending_tasks(runId);
CREATE INDEX IF NOT EXISTS idx_events_ws ON events(wsId);
CREATE INDEX IF NOT EXISTS idx_subscriptions_ws ON event_subscriptions(wsId);
CREATE INDEX IF NOT EXISTS idx_webhooks_ws ON webhooks(wsId);
CREATE INDEX IF NOT EXISTS idx_workspaces_title ON workspaces(json_extract(data, '$.title'));
CREATE INDEX IF NOT EXISTS idx_workspaces_project ON workspaces(json_extract(data, '$.projectId'));
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(json_extract(data, '$.status'));
CREATE INDEX IF NOT EXISTS idx_tasks_status ON pending_tasks(json_extract(data, '$.status'));
CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON event_subscriptions(json_extract(data, '$.eventType'));
CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON event_subscriptions(json_extract(data, '$.enabled'));
CREATE INDEX IF NOT EXISTS idx_webhooks_enabled ON webhooks(json_extract(data, '$.enabled'));
CREATE TABLE IF NOT EXISTS run_traces (
    traceId TEXT PRIMARY KEY,
    runId TEXT NOT NULL,
    nodeId TEXT NOT NULL,
    seq INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_traces_run ON run_traces(runId);
"""

_SCHEMA_VERSION = 4

_MIGRATIONS: list[tuple[int, str]] = [
    (
        2,
        "\n".join(
            [
                "CREATE INDEX IF NOT EXISTS idx_workspaces_title ON workspaces(json_extract(data, '$.title'));",
                "CREATE INDEX IF NOT EXISTS idx_workspaces_project ON workspaces(json_extract(data, '$.projectId'));",
                "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(json_extract(data, '$.status'));",
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON pending_tasks(json_extract(data, '$.status'));",
                "CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON event_subscriptions(json_extract(data, '$.eventType'));",
                "CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON event_subscriptions(json_extract(data, '$.enabled'));",
                "CREATE INDEX IF NOT EXISTS idx_webhooks_enabled ON webhooks(json_extract(data, '$.enabled'));",
            ]
        ),
    ),
    (
        3,
        "\n".join(
            [
                "CREATE TABLE IF NOT EXISTS run_traces (",
                "    traceId TEXT PRIMARY KEY,",
                "    runId TEXT NOT NULL,",
                "    nodeId TEXT NOT NULL,",
                "    seq INTEGER NOT NULL,",
                "    data TEXT NOT NULL",
                ");",
                "CREATE INDEX IF NOT EXISTS idx_run_traces_run ON run_traces(runId);",
            ]
        ),
    ),
    (
        4,
        "\n".join(
            [
                "CREATE TABLE IF NOT EXISTS scheduler_lease (",
                "    holder TEXT PRIMARY KEY,",
                "    expires_at TEXT NOT NULL",
                ");",
                "CREATE TABLE IF NOT EXISTS event_dedup (",
                "    event_id TEXT PRIMARY KEY,",
                "    ws_id TEXT NOT NULL,",
                "    seen_at TEXT NOT NULL",
                ");",
                "CREATE INDEX IF NOT EXISTS idx_event_dedup_seen ON event_dedup(seen_at);",
                "CREATE TABLE IF NOT EXISTS rate_limit_buckets (",
                "    tenant_id TEXT PRIMARY KEY,",
                "    tokens REAL NOT NULL,",
                "    last_refill TEXT NOT NULL",
                ");",
            ]
        ),
    ),
]


class _ConnectionPool:
    def __init__(self, db_path: str, size: int):
        self.db_path = db_path
        self.size = size
        self._idle: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        self._all: list[aiosqlite.Connection] = []
        self._closed = False

    async def add(self, conn: aiosqlite.Connection):
        self._all.append(conn)
        await self._idle.put(conn)

    async def acquire(self) -> aiosqlite.Connection:
        if self._closed:
            raise RuntimeError("connection pool closed")
        return await self._idle.get()

    def release(self, conn: aiosqlite.Connection):
        if self._closed:
            return
        self._idle.put_nowait(conn)

    async def close_all(self):
        self._closed = True
        while not self._idle.empty():
            try:
                self._idle.get_nowait()
            except Exception:
                break
        for conn in self._all:
            try:
                await conn.close()
            except Exception as e:
                logger.warning("pool conn close error: %s", e)
        self._all.clear()
        logger.info("db pool closed (%d conns)", self.size)


class Store:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._pool: _ConnectionPool | None = None
        self._pool_size = _resolve_pool_size(db_path)

    class _AcquiredConn:
        def __init__(self, store):
            self._store = store
            self._conn = None

        async def __aenter__(self) -> aiosqlite.Connection:
            self._conn = await self._store._pool.acquire()
            return self._conn

        async def __aexit__(self, exc_type, exc, tb):
            self._store._pool.release(self._conn)
            return False

    def acquire(self) -> "_AcquiredConn":
        return Store._AcquiredConn(self)

    async def _open_conn(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def init(self):
        self._pool = _ConnectionPool(self.db_path, self._pool_size)
        primary = await self._open_conn()
        await primary.executescript(_SCHEMA)
        await primary.commit()
        await self._run_migrations(primary)
        await self._pool.add(primary)
        for _ in range(self._pool_size - 1):
            conn = await self._open_conn()
            await conn.executescript(_SCHEMA)
            await conn.commit()
            await self._pool.add(conn)
        logger.info("db initialized: %s (WAL, pool=%d, schema v=%d)", self.db_path, self._pool_size, _SCHEMA_VERSION)

    async def _run_migrations(self, conn: aiosqlite.Connection):
        cursor = await conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current = row[0] if row else 0
        applied = 0
        for version, script in _MIGRATIONS:
            if version > current:
                await conn.executescript(script)
                await conn.execute(f"PRAGMA user_version = {version}")
                await conn.commit()
                logger.info("db migration applied: v%d", version)
                applied += 1
        if not applied and current != _SCHEMA_VERSION:
            await conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            await conn.commit()
        elif not applied:
            logger.info("db schema already at v%d", current)

    async def close(self):
        if self._pool:
            await self._pool.close_all()
            self._pool = None

    async def is_healthy(self) -> bool:
        if not self._pool:
            return False
        try:
            async with self.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.warning("db health check failed: %s", e)
            return False

    _PK_MAP: ClassVar[dict[str, str]] = {
        "workspaces": "wsId",
        "connectors": "connId",
        "skills": "skillId",
        "workflows": "wfId",
        "runs": "runId",
        "pending_tasks": "taskId",
        "templates": "templateId",
        "events": "eventId",
        "event_subscriptions": "subId",
        "webhooks": "webhookId",
    }

    _WS_COL_MAP: ClassVar[dict[str, str]] = {
        "connectors": "wsId",
        "skills": "wsId",
        "workflows": "wsId",
        "runs": "wsId",
        "pending_tasks": "wsId",
        "templates": "wsId",
        "events": "wsId",
        "event_subscriptions": "wsId",
        "webhooks": "wsId",
    }

    def _pk_col(self, table: str) -> str:
        return self._PK_MAP.get(table, table.rstrip("s") + "Id")

    @staticmethod
    def _clamp_page(offset: int = 0, limit: int = 100) -> tuple[int, int]:
        offset = max(0, int(offset))
        limit = int(limit)
        if limit < 0:
            limit = MAX_PAGE
        limit = min(limit, MAX_PAGE)
        return offset, limit

    @staticmethod
    def _load_data(raw: str) -> dict | None:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("corrupt data blob skipped: %s", e)
            return None

    async def _get_one(self, table: str, pk: str, pk_col: str | None = None) -> dict | None:
        col = pk_col or self._pk_col(table)
        async with self.acquire() as db:
            cursor = await db.execute(f"SELECT data FROM {table} WHERE {col} = ?", (pk,))
            row = await cursor.fetchone()
        if row:
            return self._load_data(row["data"])
        return None

    async def _get_many(self, table: str, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        ws_col = self._WS_COL_MAP.get(table, "wsId")
        offset, limit = self._clamp_page(offset, limit)
        async with self.acquire() as db:
            cursor = await db.execute(
                f"SELECT data FROM {table} WHERE {ws_col} = ? LIMIT ? OFFSET ?",
                (ws_id, limit, offset),
            )
            rows = await cursor.fetchall()
        return [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]

    async def _upsert(self, table: str, pk: str, data: dict, ws_id: str = "", extra_cols: dict | None = None):
        pk_col = self._pk_col(table)
        payload = json.dumps(data, default=str)
        is_root = table == "workspaces"
        if is_root:
            sql = (
                f"INSERT INTO {table} ({pk_col}, data) VALUES (?, ?) "
                f"ON CONFLICT({pk_col}) DO UPDATE SET data = excluded.data"
            )
            params = [pk, payload]
        elif extra_cols:
            ws_col = self._WS_COL_MAP.get(table, "wsId")
            cols = f"{pk_col}, {ws_col}, data, " + ", ".join(extra_cols)
            vals = "?, ?, ?, " + ", ".join(["?"] * len(extra_cols))
            updates = ", ".join([f"{c} = excluded.{c}" for c in extra_cols])
            sql = (
                f"INSERT INTO {table} ({cols}) VALUES ({vals}) "
                f"ON CONFLICT({pk_col}) DO UPDATE SET data = excluded.data, {updates}"
            )
            params = [pk, ws_id, payload, *list(extra_cols.values())]
        else:
            ws_col = self._WS_COL_MAP.get(table, "wsId")
            sql = (
                f"INSERT INTO {table} ({pk_col}, {ws_col}, data) VALUES (?, ?, ?) "
                f"ON CONFLICT({pk_col}) DO UPDATE SET data = excluded.data"
            )
            params = [pk, ws_id, payload]
        async with self.acquire() as db:
            await db.execute(sql, params)
            await db.commit()

    async def _delete(self, table: str, pk: str, pk_col: str | None = None):
        col = pk_col or self._pk_col(table)
        async with self.acquire() as db:
            await db.execute(f"DELETE FROM {table} WHERE {col} = ?", (pk,))
            await db.commit()

    async def _delete_by_workspace(self, table: str, ws_id: str):
        ws_col = self._WS_COL_MAP.get(table, "wsId")
        async with self.acquire() as db:
            await db.execute(f"DELETE FROM {table} WHERE {ws_col} = ?", (ws_id,))
            await db.commit()

    # workspace
    async def get_workspace(self, ws_id: str) -> dict | None:
        return await self._get_one("workspaces", ws_id, "wsId")

    async def list_workspaces(
        self, offset: int = 0, limit: int = 100, search: str = "", project_id: str = ""
    ) -> list[dict]:
        offset, limit = self._clamp_page(offset, limit)
        sql = "SELECT data FROM workspaces"
        conditions = []
        params = []
        if search:
            conditions.append("json_extract(data, '$.title') LIKE ?")
            params.append(f"%{search}%")
        if project_id:
            conditions.append("json_extract(data, '$.projectId') = ?")
            params.append(project_id)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.acquire() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]

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
        async with self.acquire() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                for table in child_tables:
                    ws_col = self._WS_COL_MAP.get(table, "wsId")
                    await db.execute(f"DELETE FROM {table} WHERE {ws_col} = ?", (ws_id,))
                await db.execute(
                    "DELETE FROM run_traces WHERE runId IN (SELECT runId FROM runs WHERE wsId = ?)",
                    (ws_id,),
                )
                await db.execute("DELETE FROM workspaces WHERE wsId = ?", (ws_id,))
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("workspace cascade delete failed, rolled back: %s", ws_id)
                raise
        logger.info("workspace deleted with cascade (atomic): %s", ws_id)

    # connector
    async def get_connector(self, conn_id: str) -> dict | None:
        return await self._get_one("connectors", conn_id, "connId")

    async def list_connectors(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("connectors", ws_id, offset=offset, limit=limit)

    async def save_connector(self, conn_id: str, ws_id: str, data: dict):
        await self._upsert("connectors", conn_id, data, ws_id)

    async def delete_connector(self, conn_id: str):
        await self._delete("connectors", conn_id, "connId")

    # skill
    async def get_skill(self, skill_id: str) -> dict | None:
        return await self._get_one("skills", skill_id, "skillId")

    async def list_skills(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("skills", ws_id, offset=offset, limit=limit)

    async def save_skill(self, skill_id: str, ws_id: str, data: dict):
        await self._upsert("skills", skill_id, data, ws_id)

    async def delete_skill(self, skill_id: str):
        await self._delete("skills", skill_id, "skillId")

    # workflow
    async def get_workflow(self, wf_id: str) -> dict | None:
        return await self._get_one("workflows", wf_id, "wfId")

    async def list_workflows(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("workflows", ws_id, offset=offset, limit=limit)

    async def save_workflow(self, wf_id: str, ws_id: str, data: dict):
        await self._upsert("workflows", wf_id, data, ws_id)

    async def delete_workflow(self, wf_id: str):
        await self._delete("workflows", wf_id, "wfId")

    # run
    async def get_run(self, run_id: str) -> dict | None:
        data = await self._get_one("runs", run_id, "runId")
        if data is not None:
            data["nodeTrace"] = await self.list_run_traces(run_id)
        return data

    async def list_runs(self, ws_id: str, wf_id: str | None = None, offset: int = 0, limit: int = 100) -> list[dict]:
        offset, limit = self._clamp_page(offset, limit)
        async with self.acquire() as db:
            if wf_id:
                cursor = await db.execute(
                    "SELECT data FROM runs WHERE wsId = ? AND wfId = ? LIMIT ? OFFSET ?",
                    (ws_id, wf_id, limit, offset),
                )
            else:
                cursor = await db.execute(
                    "SELECT data FROM runs WHERE wsId = ? LIMIT ? OFFSET ?",
                    (ws_id, limit, offset),
                )
            rows = await cursor.fetchall()
        runs = [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]
        if runs:
            run_ids = [r.get("runId", "") for r in runs]
            traces_by_run = await self._batch_traces(run_ids)
            for r in runs:
                r["nodeTrace"] = traces_by_run.get(r.get("runId", ""), [])
        return runs

    async def _batch_traces(self, run_ids: list[str]) -> dict[str, list[dict]]:
        if not run_ids:
            return {}
        placeholders = ",".join(["?"] * len(run_ids))
        async with self.acquire() as db:
            cursor = await db.execute(
                f"SELECT runId, data FROM run_traces WHERE runId IN ({placeholders}) ORDER BY runId, seq ASC",
                run_ids,
            )
            rows = await cursor.fetchall()
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            parsed = self._load_data(row["data"])
            if parsed is not None:
                grouped.setdefault(row["runId"], []).append(parsed)
        return grouped

    async def save_run(self, run_id: str, ws_id: str, wf_id: str, data: dict):
        persist = dict(data)
        persist["nodeTrace"] = []
        await self._upsert("runs", run_id, persist, ws_id, {"wfId": wf_id})

    async def append_run_trace(self, run_id: str, seq: int, trace: dict):
        trace_id = f"{run_id}_{seq}"
        payload = json.dumps(trace, default=str)
        async with self.acquire() as db:
            await db.execute(
                "INSERT INTO run_traces (traceId, runId, nodeId, seq, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(traceId) DO UPDATE SET data = excluded.data, nodeId = excluded.nodeId, seq = excluded.seq",
                (trace_id, run_id, trace.get("nodeId", ""), seq, payload),
            )
            await db.commit()

    async def list_run_traces(self, run_id: str) -> list[dict]:
        async with self.acquire() as db:
            cursor = await db.execute(
                "SELECT data FROM run_traces WHERE runId = ? ORDER BY seq ASC",
                (run_id,),
            )
            rows = await cursor.fetchall()
        return [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]

    async def delete_run_traces(self, run_id: str):
        async with self.acquire() as db:
            await db.execute("DELETE FROM run_traces WHERE runId = ?", (run_id,))
            await db.commit()

    async def cas_run_status(self, run_id: str, ws_id: str, wf_id: str, data: dict, expected_status: str) -> bool:
        payload = json.dumps(data, default=str)
        async with self.acquire() as db:
            cursor = await db.execute(
                "UPDATE runs SET data = ? WHERE runId = ? AND json_extract(data, '$.status') = ?",
                (payload, run_id, expected_status),
            )
            await db.commit()
            updated = cursor.rowcount > 0
        if not updated:
            logger.warning(
                "cas_run_status: no row updated run=%s expected_status=%s (race lost or not found)",
                run_id,
                expected_status,
            )
        return updated

    # pending task
    async def get_task(self, task_id: str) -> dict | None:
        return await self._get_one("pending_tasks", task_id, "taskId")

    async def list_pending_tasks(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        offset, limit = self._clamp_page(offset, limit)
        async with self.acquire() as db:
            cursor = await db.execute(
                "SELECT data FROM pending_tasks WHERE wsId = ? AND json_extract(data, '$.status') = 'pending' LIMIT ? OFFSET ?",
                (ws_id, limit, offset),
            )
            rows = await cursor.fetchall()
        return [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]

    async def save_task(self, task_id: str, ws_id: str, run_id: str, data: dict):
        await self._upsert("pending_tasks", task_id, data, ws_id, {"runId": run_id})

    async def delete_task(self, task_id: str):
        await self._delete("pending_tasks", task_id, "taskId")

    # template
    async def get_template(self, tpl_id: str) -> dict | None:
        return await self._get_one("templates", tpl_id, "templateId")

    async def list_templates(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("templates", ws_id, offset=offset, limit=limit)

    async def save_template(self, tpl_id: str, ws_id: str, data: dict):
        await self._upsert("templates", tpl_id, data, ws_id)

    async def delete_template(self, tpl_id: str):
        await self._delete("templates", tpl_id, "templateId")

    # event
    async def get_event(self, event_id: str) -> dict | None:
        return await self._get_one("events", event_id, "eventId")

    async def list_events(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("events", ws_id, offset=offset, limit=limit)

    async def save_event(self, event_id: str, ws_id: str, data: dict):
        await self._upsert("events", event_id, data, ws_id)

    async def delete_event(self, event_id: str):
        await self._delete("events", event_id, "eventId")

    # event subscription
    async def get_subscription(self, sub_id: str) -> dict | None:
        return await self._get_one("event_subscriptions", sub_id, "subId")

    async def list_subscriptions(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("event_subscriptions", ws_id, offset=offset, limit=limit)

    async def save_subscription(self, sub_id: str, ws_id: str, data: dict):
        await self._upsert("event_subscriptions", sub_id, data, ws_id)

    async def delete_subscription(self, sub_id: str):
        await self._delete("event_subscriptions", sub_id, "subId")

    async def find_matching_subscriptions(self, event_type: str, source: str = "", ws_id: str = "") -> list[dict]:
        async with self.acquire() as db:
            if ws_id:
                cursor = await db.execute(
                    "SELECT data FROM event_subscriptions WHERE wsId = ? AND json_extract(data, '$.eventType') = ? AND json_extract(data, '$.enabled') = 1",
                    (ws_id, event_type),
                )
            else:
                cursor = await db.execute(
                    "SELECT data FROM event_subscriptions WHERE json_extract(data, '$.eventType') = ? AND json_extract(data, '$.enabled') = 1",
                    (event_type,),
                )
            rows = await cursor.fetchall()
        results = [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]
        if source:
            results = [r for r in results if r.get("source") is None or r.get("source") == source]
        logger.info(
            "found %d matching subscriptions for event_type=%s source=%s ws=%s",
            len(results),
            event_type,
            source,
            ws_id,
        )
        return results

    # webhook
    async def get_webhook(self, webhook_id: str) -> dict | None:
        return await self._get_one("webhooks", webhook_id, "webhookId")

    async def list_webhooks(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("webhooks", ws_id, offset=offset, limit=limit)

    async def save_webhook(self, webhook_id: str, ws_id: str, data: dict):
        await self._upsert("webhooks", webhook_id, data, ws_id)

    async def delete_webhook(self, webhook_id: str):
        await self._delete("webhooks", webhook_id, "webhookId")

    async def find_webhooks_for_event(self, ws_id: str, event: str) -> list[dict]:
        async with self.acquire() as db:
            cursor = await db.execute(
                "SELECT data FROM webhooks WHERE wsId = ? AND json_extract(data, '$.enabled') = 1",
                (ws_id,),
            )
            rows = await cursor.fetchall()
        results = [d for d in (self._load_data(r["data"]) for r in rows) if d is not None]
        results = [r for r in results if event in r.get("events", [])]
        logger.info("found %d webhooks for ws=%s event=%s", len(results), ws_id, event)
        return results

    async def cleanup_old_runs(self, retention_days: int = 30, keep_per_ws: int = 200) -> dict:
        from datetime import datetime, timedelta

        cutoff_dt = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_iso = cutoff_dt.isoformat()
        deleted = {"runs": 0, "pending_tasks": 0, "events": 0}
        async with self.acquire() as db:
            try:
                await db.execute(
                    "DELETE FROM run_traces WHERE runId IN ("
                    "  SELECT runId FROM runs WHERE json_extract(data, '$.endTime') IS NOT NULL "
                    "  AND json_extract(data, '$.endTime') != 'null' "
                    "  AND json_extract(data, '$.endTime') < ?)",
                    (cutoff_iso,),
                )
                cur = await db.execute(
                    "DELETE FROM runs WHERE json_extract(data, '$.endTime') IS NOT NULL "
                    "AND json_extract(data, '$.endTime') != 'null' "
                    "AND json_extract(data, '$.endTime') < ?",
                    (cutoff_iso,),
                )
                deleted["runs"] = cur.rowcount
                cur = await db.execute(
                    "DELETE FROM pending_tasks WHERE json_extract(data, '$.status') IN ('approved','denied')"
                )
                deleted["pending_tasks"] = cur.rowcount
                cur = await db.execute(
                    "DELETE FROM events WHERE rowid NOT IN (  SELECT rowid FROM events ORDER BY rowid DESC LIMIT ?)",
                    (keep_per_ws * 10,),
                )
                deleted["events"] = cur.rowcount
                await db.commit()
                logger.info("retention cleanup: %s", deleted)
            except Exception:
                await db.rollback()
                logger.exception("retention cleanup failed, rolled back")
                raise
        return deleted

    # ---- distributed primitives ----

    async def try_acquire_leader(self, holder: str, ttl_seconds: int) -> bool:
        from datetime import UTC, datetime, timedelta

        expires = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
        async with self.acquire() as db:
            cur = await db.execute("SELECT expires_at FROM scheduler_lease WHERE holder = ?", (holder,))
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE scheduler_lease SET expires_at = ? WHERE holder = ?", (expires, holder))
                await db.commit()
                return True
            try:
                await db.execute("INSERT INTO scheduler_lease (holder, expires_at) VALUES (?, ?)", (holder, expires))
                await db.commit()
                return True
            except Exception as e:
                logger.warning("leader acquire race lost: %s", e)
                return False

    async def renew_leader(self, holder: str, ttl_seconds: int) -> bool:
        from datetime import UTC, datetime, timedelta

        expires = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
        async with self.acquire() as db:
            cur = await db.execute("UPDATE scheduler_lease SET expires_at = ? WHERE holder = ?", (expires, holder))
            await db.commit()
            return cur.rowcount > 0

    async def is_leader(self, holder: str) -> bool:
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        async with self.acquire() as db:
            cur = await db.execute("SELECT expires_at FROM scheduler_lease WHERE holder = ?", (holder,))
            row = await cur.fetchone()
        return row is not None and row["expires_at"] > now

    async def release_leader(self, holder: str):
        async with self.acquire() as db:
            await db.execute("DELETE FROM scheduler_lease WHERE holder = ?", (holder,))
            await db.commit()

    async def event_seen(self, event_id: str, ws_id: str, ttl_seconds: int) -> bool:
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        async with self.acquire() as db:
            cur = await db.execute("SELECT seen_at FROM event_dedup WHERE event_id = ?", (event_id,))
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE event_dedup SET seen_at = ? WHERE event_id = ?", (now.isoformat(), event_id))
                await db.commit()
                return True
            try:
                await db.execute(
                    "INSERT INTO event_dedup (event_id, ws_id, seen_at) VALUES (?, ?, ?)",
                    (event_id, ws_id, now.isoformat()),
                )
                await db.commit()
                await db.execute(
                    "DELETE FROM event_dedup WHERE seen_at < ?",
                    ((now - timedelta(seconds=ttl_seconds)).isoformat(),),
                )
                await db.commit()
                return False
            except Exception as e:
                logger.warning("event dedup race: %s", e)
                return True

    async def rate_limit_consume(self, tenant_id: str, capacity: int, refill_rate: int) -> bool:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        async with self.acquire() as db:
            cur = await db.execute(
                "SELECT tokens, last_refill FROM rate_limit_buckets WHERE tenant_id = ?", (tenant_id,)
            )
            row = await cur.fetchone()
            if row is None:
                tokens = float(capacity)
                last_refill = now.isoformat()
                await db.execute(
                    "INSERT INTO rate_limit_buckets (tenant_id, tokens, last_refill) VALUES (?, ?, ?)",
                    (tenant_id, tokens, last_refill),
                )
            else:
                last_refill = datetime.fromisoformat(row["last_refill"])
                elapsed = (now - last_refill).total_seconds()
                tokens = min(float(capacity), float(row["tokens"]) + elapsed * refill_rate)
            if tokens < 1.0:
                await db.execute(
                    "UPDATE rate_limit_buckets SET tokens = ?, last_refill = ? WHERE tenant_id = ?",
                    (tokens, now.isoformat(), tenant_id),
                )
                await db.commit()
                return False
            tokens -= 1.0
            await db.execute(
                "UPDATE rate_limit_buckets SET tokens = ?, last_refill = ? WHERE tenant_id = ?",
                (tokens, now.isoformat(), tenant_id),
            )
            await db.commit()
            return True
