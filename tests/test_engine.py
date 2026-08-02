import pytest

from fsb.db.store import Store
from fsb.engine.router import IntentRouter
from fsb.engine.runner import WorkflowRunner
from fsb.engine.scheduler import WorkflowScheduler
from fsb.models.common import NodeType, ScheduleType
from fsb.models.workflow import (
    GraphDefinition,
    NodeConfig,
    ScheduleConfig,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)


def _make_workflow(name: str, slash: str, nodes: list = None, edges: list = None) -> Workflow:
    default_nodes = [
        WorkflowNode(id="n_start", type=NodeType.START_NODE),
        WorkflowNode(id="n_end", type=NodeType.END_NODE),
    ]
    default_edges = [WorkflowEdge(source="n_start", target="n_end")]
    return Workflow(
        name=name,
        slashCommand=slash,
        graphDefinition=GraphDefinition(
            nodes=nodes or default_nodes,
            edges=edges or default_edges,
            entryNode="n_start",
        ),
    )


class TestIntentRouter:
    @pytest.mark.asyncio
    async def test_exact_slash_match(self):
        store = Store(db_path=":memory:")
        await store.init()
        wf1 = _make_workflow("invoice-chase", "/invoice-chase")
        wf2 = _make_workflow("lead-nurture", "/lead-nurture")
        await store.save_workflow(wf1.wfId, "ws_1", wf1.model_dump(mode="json"))
        await store.save_workflow(wf2.wfId, "ws_1", wf2.model_dump(mode="json"))
        router = IntentRouter(store)
        result = await router.match("ws_1", "/invoice-chase")
        assert result is not None
        assert result.name == "invoice-chase"

    @pytest.mark.asyncio
    async def test_fuzzy_match(self):
        store = Store(db_path=":memory:")
        await store.init()
        wf1 = _make_workflow("invoice-chase", "/invoice-chase")
        await store.save_workflow(wf1.wfId, "ws_1", wf1.model_dump(mode="json"))
        router = IntentRouter(store)
        result = await router.match("ws_1", "chase invoice")
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_match(self):
        store = Store(db_path=":memory:")
        await store.init()
        router = IntentRouter(store)
        result = await router.match("ws_1", "/nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_slash_commands(self):
        store = Store(db_path=":memory:")
        await store.init()
        wf1 = _make_workflow("a", "/a")
        wf2 = _make_workflow("b", "/b")
        await store.save_workflow(wf1.wfId, "ws_1", wf1.model_dump(mode="json"))
        await store.save_workflow(wf2.wfId, "ws_1", wf2.model_dump(mode="json"))
        router = IntentRouter(store)
        cmds = await router.list_slash_commands("ws_1")
        assert len(cmds) == 2


class TestGraphValidation:
    @pytest.mark.asyncio
    async def test_valid_simple_graph(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        wf = _make_workflow("valid", "/valid")
        runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_missing_end_node(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        wf = Workflow(
            name="bad",
            slashCommand="/bad",
            graphDefinition=GraphDefinition(
                nodes=[WorkflowNode(id="n_start", type=NodeType.START_NODE)],
                edges=[],
                entryNode="n_start",
            ),
        )
        with pytest.raises(ValueError, match="END_NODE"):
            runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_missing_start_node(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        wf = Workflow(
            name="bad",
            slashCommand="/bad",
            graphDefinition=GraphDefinition(
                nodes=[WorkflowNode(id="n_end", type=NodeType.END_NODE)],
                edges=[],
                entryNode="n_start",
            ),
        )
        with pytest.raises(ValueError, match="START_NODE"):
            runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_cycle_detection(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_a", type=NodeType.SKILL_NODE),
            WorkflowNode(id="n_b", type=NodeType.SKILL_NODE),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_a"),
            WorkflowEdge(source="n_a", target="n_b"),
            WorkflowEdge(source="n_b", target="n_a"),
            WorkflowEdge(source="n_b", target="n_end"),
        ]
        wf = Workflow(
            name="cyclic",
            slashCommand="/cyclic",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        with pytest.raises(ValueError, match="cycle"):
            runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_write_connector_needs_approval_gate(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_write", type=NodeType.CONNECTOR_NODE, config=NodeConfig(action="send_email")),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_write"),
            WorkflowEdge(source="n_write", target="n_end"),
        ]
        wf = Workflow(
            name="no-approval",
            slashCommand="/no-approval",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        with pytest.raises(ValueError, match="approval"):
            runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_write_permission_needs_approval_gate(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_write", type=NodeType.CONNECTOR_NODE, config=NodeConfig(action="custom_action", permission="write")),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_write"),
            WorkflowEdge(source="n_write", target="n_end"),
        ]
        wf = Workflow(
            name="write-perm-no-gate",
            slashCommand="/write-perm-no-gate",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        with pytest.raises(ValueError, match="approval"):
            runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_write_with_approval_gate_passes(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_gate", type=NodeType.APPROVAL_GATE_NODE),
            WorkflowNode(id="n_write", type=NodeType.CONNECTOR_NODE, config=NodeConfig(action="send_email", permission="write")),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_gate"),
            WorkflowEdge(source="n_gate", target="n_write"),
            WorkflowEdge(source="n_write", target="n_end"),
        ]
        wf = Workflow(
            name="with-gate",
            slashCommand="/with-gate",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_dangling_branch_detected(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_a", type=NodeType.SKILL_NODE),
            WorkflowNode(id="n_b", type=NodeType.SKILL_NODE),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_a"),
            WorkflowEdge(source="n_start", target="n_b"),
            WorkflowEdge(source="n_a", target="n_end"),
        ]
        wf = Workflow(
            name="dangling",
            slashCommand="/dangling",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        with pytest.raises(ValueError, match="converge"):
            runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_all_branches_converge_passes(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_a", type=NodeType.SKILL_NODE),
            WorkflowNode(id="n_b", type=NodeType.SKILL_NODE),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_a"),
            WorkflowEdge(source="n_start", target="n_b"),
            WorkflowEdge(source="n_a", target="n_end"),
            WorkflowEdge(source="n_b", target="n_end"),
        ]
        wf = Workflow(
            name="converge",
            slashCommand="/converge",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        runner._validate_graph(wf.graphDefinition)

    @pytest.mark.asyncio
    async def test_read_connector_no_approval_needed(self):
        store = Store(db_path=":memory:")
        await store.init()
        runner = WorkflowRunner(store)
        nodes = [
            WorkflowNode(id="n_start", type=NodeType.START_NODE),
            WorkflowNode(id="n_read", type=NodeType.CONNECTOR_NODE, config=NodeConfig(action="get_data", permission="read")),
            WorkflowNode(id="n_end", type=NodeType.END_NODE),
        ]
        edges = [
            WorkflowEdge(source="n_start", target="n_read"),
            WorkflowEdge(source="n_read", target="n_end"),
        ]
        wf = Workflow(
            name="read-only",
            slashCommand="/read-only",
            graphDefinition=GraphDefinition(nodes=nodes, edges=edges, entryNode="n_start"),
        )
        runner._validate_graph(wf.graphDefinition)


class TestScheduler:
    @pytest.mark.asyncio
    async def test_register_unregister(self):
        store = Store(db_path=":memory:")
        await store.init()
        scheduler = WorkflowScheduler(store)
        scheduler.start()
        wf = _make_workflow("scheduled-wf", "/scheduled-wf")
        wf.schedule = ScheduleConfig(type=ScheduleType.CRON, cron="0 9 * * 1")
        await store.save_workflow(wf.wfId, "ws_1", wf.model_dump(mode="json"))
        await scheduler.register("ws_1", wf.wfId)
        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        await scheduler.unregister("ws_1", wf.wfId)
        jobs = scheduler.list_jobs()
        assert len(jobs) == 0
        scheduler.stop()
