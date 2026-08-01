import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..connectors.registry import get_builtin_connectors
from ..db.store import Store
from ..models.common import AuthStatus, ConnectorMeta, utc_now
from ..models.connector import Connector, ConnectorCreate, ConnectorUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace/{wsId}/connector", tags=["connector"])

meta_router = APIRouter(prefix="/connector-meta", tags=["connector-meta"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


@router.post("", response_model=Connector)
async def create_connector(wsId: str, body: ConnectorCreate):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    conn = Connector(workspaceId=wsId, **body.model_dump())
    conn.authStatus = AuthStatus.CONNECTED
    conn.connectedAt = utc_now()
    await store.save_connector(conn.connId, wsId, conn.model_dump(mode="json"))
    ws["connectorIds"] = list(set(ws.get("connectorIds", []) + [conn.connectorKey]))
    await store.save_workspace(wsId, ws)
    logger.info("connector created: %s in ws %s", conn.connId, wsId)
    return conn


@router.get("", response_model=list[Connector])
async def list_connectors(wsId: str, offset: int = 0, limit: int = 100):
    store = get_store()
    items = await store.list_connectors(wsId, offset=offset, limit=limit)
    return [Connector(**d) for d in items]


@router.put("/{connId}", response_model=Connector)
async def update_connector(wsId: str, connId: str, body: ConnectorUpdate):
    store = get_store()
    data = await store.get_connector(connId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="connector not found")
    conn = Connector(**data)
    update = body.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(conn, k, v)
    await store.save_connector(conn.connId, wsId, conn.model_dump(mode="json"))
    logger.info("connector updated: %s", connId)
    return conn


@router.post("/{connId}/disconnect")
async def disconnect_connector(wsId: str, connId: str):
    store = get_store()
    data = await store.get_connector(connId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="connector not found")
    conn = Connector(**data)
    conn.authStatus = AuthStatus.DISCONNECTED
    await store.save_connector(conn.connId, wsId, conn.model_dump(mode="json"))
    logger.info("connector disconnected: %s", connId)
    return {"success": True}


@router.post("/{connId}/refresh")
async def refresh_connector(wsId: str, connId: str):
    store = get_store()
    data = await store.get_connector(connId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="connector not found")
    conn = Connector(**data)
    conn.authStatus = AuthStatus.CONNECTED
    conn.lastRefreshAt = utc_now()
    await store.save_connector(conn.connId, wsId, conn.model_dump(mode="json"))
    logger.info("connector refreshed: %s", connId)
    return {"success": True}


@meta_router.get("", response_model=list[ConnectorMeta])
async def list_connector_meta():
    return get_builtin_connectors()


@meta_router.get("/{connectorKey}", response_model=ConnectorMeta)
async def get_connector_meta(connectorKey: str):
    for m in get_builtin_connectors():
        if m.connectorKey == connectorKey:
            return m
    raise HTTPException(status_code=404, detail="connector meta not found")
