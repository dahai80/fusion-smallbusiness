import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from fsb.db.store import Store
from fsb.tenant_dep import ws_tenant_dep


def _make_app(verify_jwt, require_jwt=True):
    from fastapi import APIRouter, Depends, FastAPI
    from fusion_core.tenant import install_tenant_middleware

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    router = APIRouter(prefix="/workspace/{wsId}", dependencies=[Depends(ws_tenant_dep)])

    @router.get("/skill", response_model=list[dict])
    async def list_skills(wsId: str):
        return [{"wsId": wsId}]

    app.include_router(router)
    install_tenant_middleware(app, verify_jwt=verify_jwt, require_jwt=require_jwt)
    return app


def _valid_jwt():
    import base64
    import json
    import time

    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"tid": "tenant_A", "sub": "user1", "role": "owner", "exp": int(time.time()) + 3600}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


@pytest_asyncio.fixture
async def auth_client(monkeypatch):
    test_db = "test_fsb_auth.db"
    store = Store(db_path=test_db)
    await store.init()

    def verify(token):
        if token == "revoked-token":
            raise PermissionError("token revoked")
        return {"tid": "tenant_A", "role": "owner", "scope": []}

    app = _make_app(verify_jwt=verify, require_jwt=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10.0) as c:
        yield c
    await store.close()
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.mark.asyncio
async def test_unauthenticated_workspace_request_401(auth_client):
    resp = await auth_client.get("/workspace/tenant_A/skill", headers={"X-Tenant-Id": "tenant_A"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_tenant_header_401(auth_client):
    resp = await auth_client.get(
        "/workspace/tenant_A/skill",
        headers={"Authorization": f"Bearer {_valid_jwt()}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_wsId_403(auth_client):
    resp = await auth_client.get(
        "/workspace/tenant_B/skill",
        headers={"X-Tenant-Id": "tenant_A", "Authorization": f"Bearer {_valid_jwt()}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_valid_tenant_200(auth_client):
    resp = await auth_client.get(
        "/workspace/tenant_A/skill",
        headers={"X-Tenant-Id": "tenant_A", "Authorization": f"Bearer {_valid_jwt()}"},
    )
    assert resp.status_code == 200
    assert resp.json() == [{"wsId": "tenant_A"}]


@pytest.mark.asyncio
async def test_revoked_token_401(auth_client):
    resp = await auth_client.get(
        "/workspace/tenant_A/skill",
        headers={"X-Tenant-Id": "tenant_A", "Authorization": "Bearer revoked-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tenant_mismatch_header_vs_jwt_401(auth_client):
    jwt_a = _valid_jwt()
    resp = await auth_client.get(
        "/workspace/tenant_A/skill",
        headers={"X-Tenant-Id": "tenant_X", "Authorization": f"Bearer {jwt_a}"},
    )
    assert resp.status_code == 401
