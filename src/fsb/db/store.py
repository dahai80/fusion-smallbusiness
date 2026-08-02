import json
import logging
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = "fsb_data.db"

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
"""


class Store:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        logger.info("db initialized: %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()
            logger.info("db closed")

    _PK_MAP = {
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

    _WS_COL_MAP = {
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

    async def _get_one(self, table: str, pk: str, pk_col: str = None) -> Optional[dict]:
        col = pk_col or self._pk_col(table)
        cursor = await self._db.execute(f"SELECT data FROM {table} WHERE {col} = ?", (pk,))
        row = await cursor.fetchone()
        if row:
            return json.loads(row["data"])
        return None

    async def _get_many(self, table: str, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        ws_col = self._WS_COL_MAP.get(table, "wsId")
        cursor = await self._db.execute(
            f"SELECT data FROM {table} WHERE {ws_col} = ? LIMIT ? OFFSET ?",
            (ws_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [json.loads(r["data"]) for r in rows]

    async def _upsert(self, table: str, pk: str, data: dict, ws_id: str = "", extra_cols: dict = None):
        pk_col = self._pk_col(table)
        payload = json.dumps(data, default=str)
        is_root = table == "workspaces"
        if is_root:
            sql = f"INSERT OR REPLACE INTO {table} ({pk_col}, data) VALUES (?, ?)"
            params = [pk, payload]
        elif extra_cols:
            ws_col = self._WS_COL_MAP.get(table, "wsId")
            cols = f"{pk_col}, {ws_col}, data, " + ", ".join(extra_cols.keys())
            vals = "?, ?, ?, " + ", ".join(["?"] * len(extra_cols))
            sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({vals})"
            params = [pk, ws_id, payload] + list(extra_cols.values())
        else:
            ws_col = self._WS_COL_MAP.get(table, "wsId")
            sql = f"INSERT OR REPLACE INTO {table} ({pk_col}, {ws_col}, data) VALUES (?, ?, ?)"
            params = [pk, ws_id, payload]
        await self._db.execute(sql, params)
        await self._db.commit()

    async def _delete(self, table: str, pk: str, pk_col: str = None):
        col = pk_col or self._pk_col(table)
        await self._db.execute(f"DELETE FROM {table} WHERE {col} = ?", (pk,))
        await self._db.commit()

    async def _delete_by_workspace(self, table: str, ws_id: str):
        ws_col = self._WS_COL_MAP.get(table, "wsId")
        await self._db.execute(f"DELETE FROM {table} WHERE {ws_col} = ?", (ws_id,))
        await self._db.commit()

    # workspace
    async def get_workspace(self, ws_id: str) -> Optional[dict]:
        return await self._get_one("workspaces", ws_id, "wsId")

    async def list_workspaces(self, offset: int = 0, limit: int = 100, search: str = "", project_id: str = "") -> list[dict]:
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
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [json.loads(r["data"]) for r in rows]

    async def save_workspace(self, ws_id: str, data: dict):
        await self._upsert("workspaces", ws_id, data)

    async def delete_workspace(self, ws_id: str):
        for table in ["connectors", "skills", "workflows", "runs", "pending_tasks", "templates", "events", "event_subscriptions", "webhooks"]:
            await self._delete_by_workspace(table, ws_id)
        await self._delete("workspaces", ws_id, "wsId")
        logger.info("workspace deleted with cascade: %s", ws_id)

    # connector
    async def get_connector(self, conn_id: str) -> Optional[dict]:
        return await self._get_one("connectors", conn_id, "connId")

    async def list_connectors(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("connectors", ws_id, offset=offset, limit=limit)

    async def save_connector(self, conn_id: str, ws_id: str, data: dict):
        await self._upsert("connectors", conn_id, data, ws_id)

    async def delete_connector(self, conn_id: str):
        await self._delete("connectors", conn_id, "connId")

    # skill
    async def get_skill(self, skill_id: str) -> Optional[dict]:
        return await self._get_one("skills", skill_id, "skillId")

    async def list_skills(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("skills", ws_id, offset=offset, limit=limit)

    async def save_skill(self, skill_id: str, ws_id: str, data: dict):
        await self._upsert("skills", skill_id, data, ws_id)

    async def delete_skill(self, skill_id: str):
        await self._delete("skills", skill_id, "skillId")

    # workflow
    async def get_workflow(self, wf_id: str) -> Optional[dict]:
        return await self._get_one("workflows", wf_id, "wfId")

    async def list_workflows(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("workflows", ws_id, offset=offset, limit=limit)

    async def save_workflow(self, wf_id: str, ws_id: str, data: dict):
        await self._upsert("workflows", wf_id, data, ws_id)

    async def delete_workflow(self, wf_id: str):
        await self._delete("workflows", wf_id, "wfId")

    # run
    async def get_run(self, run_id: str) -> Optional[dict]:
        return await self._get_one("runs", run_id, "runId")

    async def list_runs(self, ws_id: str, wf_id: str = None, offset: int = 0, limit: int = 100) -> list[dict]:
        if wf_id:
            cursor = await self._db.execute(
                "SELECT data FROM runs WHERE wsId = ? AND wfId = ? LIMIT ? OFFSET ?",
                (ws_id, wf_id, limit, offset),
            )
        else:
            cursor = await self._db.execute(
                "SELECT data FROM runs WHERE wsId = ? LIMIT ? OFFSET ?",
                (ws_id, limit, offset),
            )
        rows = await cursor.fetchall()
        return [json.loads(r["data"]) for r in rows]

    async def save_run(self, run_id: str, ws_id: str, wf_id: str, data: dict):
        await self._upsert("runs", run_id, data, ws_id, {"wfId": wf_id})

    # pending task
    async def get_task(self, task_id: str) -> Optional[dict]:
        return await self._get_one("pending_tasks", task_id, "taskId")

    async def list_pending_tasks(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT data FROM pending_tasks WHERE wsId = ? AND json_extract(data, '$.status') = 'pending' LIMIT ? OFFSET ?",
            (ws_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [json.loads(r["data"]) for r in rows]

    async def save_task(self, task_id: str, ws_id: str, run_id: str, data: dict):
        await self._upsert("pending_tasks", task_id, data, ws_id, {"runId": run_id})

    async def delete_task(self, task_id: str):
        await self._delete("pending_tasks", task_id, "taskId")

    # template
    async def get_template(self, tpl_id: str) -> Optional[dict]:
        return await self._get_one("templates", tpl_id, "templateId")

    async def list_templates(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("templates", ws_id, offset=offset, limit=limit)

    async def save_template(self, tpl_id: str, ws_id: str, data: dict):
        await self._upsert("templates", tpl_id, data, ws_id)

    async def delete_template(self, tpl_id: str):
        await self._delete("templates", tpl_id, "templateId")

    # event
    async def get_event(self, event_id: str) -> Optional[dict]:
        return await self._get_one("events", event_id, "eventId")

    async def list_events(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("events", ws_id, offset=offset, limit=limit)

    async def save_event(self, event_id: str, ws_id: str, data: dict):
        await self._upsert("events", event_id, data, ws_id)

    async def delete_event(self, event_id: str):
        await self._delete("events", event_id, "eventId")

    # event subscription
    async def get_subscription(self, sub_id: str) -> Optional[dict]:
        return await self._get_one("event_subscriptions", sub_id, "subId")

    async def list_subscriptions(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("event_subscriptions", ws_id, offset=offset, limit=limit)

    async def save_subscription(self, sub_id: str, ws_id: str, data: dict):
        await self._upsert("event_subscriptions", sub_id, data, ws_id)

    async def delete_subscription(self, sub_id: str):
        await self._delete("event_subscriptions", sub_id, "subId")

    async def find_matching_subscriptions(self, event_type: str, source: str = "") -> list[dict]:
        cursor = await self._db.execute(
            "SELECT data FROM event_subscriptions WHERE json_extract(data, '$.eventType') = ? AND json_extract(data, '$.enabled') = 1",
            (event_type,),
        )
        rows = await cursor.fetchall()
        results = [json.loads(r["data"]) for r in rows]
        if source:
            results = [r for r in results if r.get("source") is None or r.get("source") == source]
        logger.info("found %d matching subscriptions for event_type=%s source=%s", len(results), event_type, source)
        return results

    # webhook
    async def get_webhook(self, webhook_id: str) -> Optional[dict]:
        return await self._get_one("webhooks", webhook_id, "webhookId")

    async def list_webhooks(self, ws_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        return await self._get_many("webhooks", ws_id, offset=offset, limit=limit)

    async def save_webhook(self, webhook_id: str, ws_id: str, data: dict):
        await self._upsert("webhooks", webhook_id, data, ws_id)

    async def delete_webhook(self, webhook_id: str):
        await self._delete("webhooks", webhook_id, "webhookId")

    async def find_webhooks_for_event(self, ws_id: str, event: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT data FROM webhooks WHERE wsId = ? AND json_extract(data, '$.enabled') = 1",
            (ws_id,),
        )
        rows = await cursor.fetchall()
        results = [json.loads(r["data"]) for r in rows]
        results = [r for r in results if event in r.get("events", [])]
        logger.info("found %d webhooks for ws=%s event=%s", len(results), ws_id, event)
        return results
