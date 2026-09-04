import pytest

from fsb.db.store import Store
from fsb.engine.runner import WorkflowRunner
from fsb.engine.secret_crypto import decrypt_secret, encrypt_secret, is_encrypted
from fsb.models.common import NodeType, TriggerType
from fsb.models.workflow import (
    GraphDefinition,
    NodeConfig,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)


class TestSecretCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        master = "test-master-key-123"
        enc = encrypt_secret("my-secret-token", master)
        assert enc != "my-secret-token"
        assert is_encrypted(enc)
        assert decrypt_secret(enc, master) == "my-secret-token"

    def test_no_master_key_passthrough(self):
        enc = encrypt_secret("plain", "")
        assert enc == "plain"
        assert decrypt_secret("plain", "") == "plain"

    def test_empty_value(self):
        assert encrypt_secret("", "key") == ""
        assert decrypt_secret("", "key") == ""

    def test_tampered_ciphertext_rejected(self):
        master = "master-key"
        enc = encrypt_secret("secret", master)
        tampered = enc[:-4] + "AAAA"
        assert decrypt_secret(tampered, master) == ""

    def test_wrong_key_rejected(self):
        enc = encrypt_secret("secret", "key-A")
        assert decrypt_secret(enc, "key-B") == ""


class TestRunRetention:
    @pytest.mark.asyncio
    async def test_cleanup_old_runs_safe(self):
        store = Store(db_path=":memory:")
        await store.init()
        result = await store.cleanup_old_runs(retention_days=30)
        assert isinstance(result, dict)
        assert "runs" in result and "pending_tasks" in result and "events" in result
        await store.close()


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_oversize_body_rejected(self, client):
        big = {"title": "x" * (5 * 1024 * 1024)}
        resp = await client.post("/api/v1/fsb/workspace", json=big)
        assert resp.status_code in (413, 422)


class TestDbConcurrency:
    @pytest.mark.asyncio
    async def test_parallel_writes_no_lock(self, tmp_path):
        db_file = str(tmp_path / "concurrency.db")
        store = Store(db_path=db_file)
        await store.init()
        import asyncio

        async def write_one(i):
            await store.save_workspace(f"ws_{i}", {"wsId": f"ws_{i}", "title": f"ws-{i}"})

        await asyncio.gather(*(write_one(i) for i in range(40)))
        wses = await store.list_workspaces(limit=200)
        ids = {w["wsId"] for w in wses}
        assert {f"ws_{i}" for i in range(40)} <= ids
        await store.close()

    @pytest.mark.asyncio
    async def test_pool_health(self, tmp_path):
        db_file = str(tmp_path / "pool.db")
        store = Store(db_path=db_file)
        await store.init()
        assert store._pool_size > 1
        assert await store.is_healthy() is True
        await store.close()
        assert await store.is_healthy() is False


class TestRunTracePersistence:
    @pytest.mark.asyncio
    async def test_traces_persist_and_blob_stays_empty(self, tmp_path):
        db_file = str(tmp_path / "traces.db")
        store = Store(db_path=db_file)
        await store.init()

        nodes = [WorkflowNode(id="n_start", type=NodeType.START_NODE)]
        edges = []
        for i in range(12):
            nid = f"n_skill_{i}"
            nodes.append(
                WorkflowNode(
                    id=nid,
                    type=NodeType.SKILL_NODE,
                    config=NodeConfig(skillId="noop", label=f"step-{i}"),
                )
            )
            edges.append(WorkflowEdge(source=f"n_skill_{i - 1}" if i > 0 else "n_start", target=nid))
        nodes.append(WorkflowNode(id="n_out", type=NodeType.OUTPUT_NODE, config=NodeConfig(outputKey="result")))
        edges.append(WorkflowEdge(source="n_skill_11", target="n_out"))
        nodes.append(WorkflowNode(id="n_end", type=NodeType.END_NODE))
        edges.append(WorkflowEdge(source="n_out", target="n_end"))

        wf = Workflow(
            name="trace-perf",
            slashCommand="/trace-perf",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        await store.save_workspace("ws_t", {"wsId": "ws_t", "title": "t"})
        await store.save_workflow(wf.wfId, "ws_t", wf.model_dump(mode="json"))

        runner = WorkflowRunner(store)
        run = await runner.start("ws_t", wf.wfId, input_data={"q": "hello"}, trigger_type=TriggerType.MANUAL)

        persisted = await store.get_run(run.runId)
        assert persisted is not None
        traces = await store.list_run_traces(run.runId)
        assert len(persisted["nodeTrace"]) == len(traces)
        assert len(traces) >= 13

        async with store.acquire() as db:
            cursor = await db.execute("SELECT data FROM runs WHERE runId = ?", (run.runId,))
            row = await cursor.fetchone()
        blob = store._load_data(row["data"])
        assert blob["nodeTrace"] == []

        node_ids = {t["nodeId"] for t in traces}
        assert "n_end" in node_ids and "n_skill_0" in node_ids and "n_out" in node_ids

        await store.close()
