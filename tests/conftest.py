import os

os.environ.setdefault("FSB_STANDALONE_MODE", "true")
os.environ.setdefault("FSB_RATE_LIMIT_CAPACITY", "100000")
os.environ.setdefault("FSB_RATE_LIMIT_REFILL", "100000")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from fsb.app import app, app_state
from fsb.config import fsb_config
from fsb.db.store import Store

fsb_config.reload()


@pytest_asyncio.fixture(scope="session")
async def client():
    test_db = "test_fsb_data.db"
    app_state.store = Store(db_path=test_db)
    await app_state.store.init()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10.0) as c:
        yield c
    await app_state.store.close()
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest_asyncio.fixture
async def ws(client):
    resp = await client.post("/api/v1/fsb/workspace", json={"title": "test-ws"})
    assert resp.status_code == 200
    ws_id = resp.json()["wsId"]
    yield ws_id
