import logging

from ..db.store import Store
from ..models.common import NodeType, RunStatus, TriggerType, utc_now
from ..models.execution import ContextSandbox, NodeTrace, PendingTask, RunInstance
from ..models.workflow import GraphDefinition, Workflow, WorkflowNode

logger = logging.getLogger(__name__)


class WorkflowRunner:
    def __init__(self, store: Store):
        self.store = store

    async def start(
        self,
        ws_id: str,
        wf_id: str,
        input_data: dict | None = None,
        triggered_by: str = "",
        trigger_type: TriggerType = TriggerType.MANUAL,
    ) -> RunInstance:
        wf_data = await self.store.get_workflow(wf_id)
        if not wf_data:
            raise ValueError(f"workflow not found: {wf_id}")
        wf = Workflow(**wf_data)

        self._validate_graph(wf.graphDefinition)

        ws_data = await self.store.get_workspace(ws_id)
        variables = {}
        if ws_data:
            for v in ws_data.get("variables", []):
                variables[v["key"]] = v["value"]

        run = RunInstance(
            workspaceId=ws_id,
            workflowId=wf_id,
            triggerType=trigger_type,
            triggeredBy=triggered_by,
            status=RunStatus.RUNNING,
            contextSandbox=ContextSandbox(
                inputData=input_data or {},
                variables=variables,
            ),
        )
        await self.store.save_run(run.runId, ws_id, wf_id, run.model_dump(mode="json"))
        logger.info("run started: %s for wf %s", run.runId, wf_id)

        await self._execute_graph(run, wf.graphDefinition)
        return run

    async def resume(self, run_id: str, decision: str):
        run_data = await self.store.get_run(run_id)
        if not run_data:
            raise ValueError(f"run not found: {run_id}")
        run = RunInstance(**run_data)
        if run.status != RunStatus.PAUSED:
            logger.warning("run %s not paused (status=%s), skip resume", run_id, run.status)
            return

        wf_data = await self.store.get_workflow(run.workflowId)
        if not wf_data:
            raise ValueError(f"workflow not found: {run.workflowId}")
        wf = Workflow(**wf_data)

        run.status = RunStatus.RUNNING
        await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))

        current_node = self._find_node(wf.graphDefinition, run.currentNodeId)
        if current_node and current_node.type == NodeType.APPROVAL_GATE_NODE:
            trace = self._find_or_create_trace(run, current_node.id)
            trace.exitTime = utc_now()
            trace.status = f"paused_then_{decision}"
            trace.output = {"action": decision}

        next_nodes = self._get_next_nodes(wf.graphDefinition, run.currentNodeId, decision)
        for node in next_nodes:
            await self._execute_node(run, node, wf.graphDefinition)

        if run.status == RunStatus.RUNNING:
            run.status = RunStatus.COMPLETED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
            logger.info("run completed after resume: %s", run_id)
            await self._dispatch_webhooks(run)

    def _validate_graph(self, graph: GraphDefinition):
        node_ids = {n.id for n in graph.nodes}
        start_nodes = [n for n in graph.nodes if n.type == NodeType.START_NODE]
        end_nodes = [n for n in graph.nodes if n.type == NodeType.END_NODE]
        if not start_nodes:
            raise ValueError("graph must have a START_NODE")
        if not end_nodes:
            raise ValueError("graph must have an END_NODE")

        for edge in graph.edges:
            if edge.source not in node_ids:
                raise ValueError(f"edge source not found: {edge.source}")
            if edge.target not in node_ids:
                raise ValueError(f"edge target not found: {edge.target}")

        if self._has_cycle(graph):
            raise ValueError("graph contains a cycle")

        dangling = self._find_dangling_branches(graph)
        if dangling:
            raise ValueError(f"branches do not converge to END_NODE: {dangling}")

        write_nodes = [
            n for n in graph.nodes
            if n.type == NodeType.CONNECTOR_NODE
            and n.config
            and self._is_write_node(n)
        ]
        for wn in write_nodes:
            has_gate_upstream = self._has_approval_gate_upstream(graph, wn.id)
            if not has_gate_upstream:
                raise ValueError(
                    f"write connector node {wn.id} must have approval gate upstream"
                )

        logger.info("graph validation passed: %d nodes, %d edges", len(graph.nodes), len(graph.edges))

    def _is_write_node(self, node) -> bool:
        if node.config.permission == "write":
            return True
        action = (node.config.action or "").lower()
        write_keywords = ("send", "create", "update", "delete", "write", "post", "put", "patch")
        return any(kw in action for kw in write_keywords)

    def _find_dangling_branches(self, graph: GraphDefinition) -> list[str]:
        end_ids = {n.id for n in graph.nodes if n.type == NodeType.END_NODE}
        reverse_adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
        for e in graph.edges:
            reverse_adj[e.target].append(e.source)

        reachable_to_end: set[str] = set()
        for eid in end_ids:
            stack = [eid]
            while stack:
                cur = stack.pop()
                if cur in reachable_to_end:
                    continue
                reachable_to_end.add(cur)
                stack.extend(reverse_adj.get(cur, []))

        dangling = [
            n.id for n in graph.nodes
            if n.id not in reachable_to_end and n.type != NodeType.END_NODE
        ]
        return dangling

    def _has_cycle(self, graph: GraphDefinition) -> bool:
        adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
        for e in graph.edges:
            adj[e.source].append(e.target)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n.id: WHITE for n in graph.nodes}

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for nb in adj.get(node_id, []):
                if color[nb] == GRAY:
                    return True
                if color[nb] == WHITE and dfs(nb):
                    return True
            color[node_id] = BLACK
            return False

        return any(color[n.id] == WHITE and dfs(n.id) for n in graph.nodes)

    def _has_approval_gate_upstream(self, graph: GraphDefinition, node_id: str) -> bool:
        reverse_adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
        for e in graph.edges:
            reverse_adj[e.target].append(e.source)

        visited = set()
        stack = list(reverse_adj.get(node_id, []))
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            cur_node = self._find_node(graph, cur)
            if cur_node and cur_node.type == NodeType.APPROVAL_GATE_NODE:
                return True
            stack.extend(reverse_adj.get(cur, []))
        return False

    async def _execute_graph(self, run: RunInstance, graph: GraphDefinition):
        entry_node = self._find_node(graph, graph.entryNode)
        if not entry_node:
            run.status = RunStatus.FAILED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
            return

        next_nodes = self._get_next_nodes(graph, entry_node.id)
        for node in next_nodes:
            await self._execute_node(run, node, graph)

        if run.status == RunStatus.RUNNING:
            run.status = RunStatus.COMPLETED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
            logger.info("run completed: %s", run.runId)
            await self._dispatch_webhooks(run)

    async def _execute_node(self, run: RunInstance, node: WorkflowNode, graph: GraphDefinition):
        logger.info("executing node: %s type=%s run=%s", node.id, node.type, run.runId)
        trace = NodeTrace(nodeId=node.id, input=self._build_node_input(run, node))
        run.nodeTrace.append(trace)
        run.currentNodeId = node.id

        try:
            if node.type == NodeType.START_NODE:
                trace.status = "success"
                trace.output = {}
                trace.exitTime = utc_now()
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.CONNECTOR_NODE:
                result = await self._execute_connector(run, node)
                trace.status = "success"
                trace.output = result
                trace.exitTime = utc_now()
                run.contextSandbox.snapshots[node.config.connectorId] = result
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.SKILL_NODE:
                result = await self._execute_skill(run, node)
                trace.status = "success"
                trace.output = result
                trace.exitTime = utc_now()
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.CONDITION_NODE:
                result = await self._execute_condition(run, node)
                trace.status = "success"
                trace.output = result
                trace.exitTime = utc_now()
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
                branch = result.get("branch", "default")
                next_nodes = self._get_next_nodes(graph, node.id, branch)
                for n in next_nodes:
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.APPROVAL_GATE_NODE:
                trace.status = "paused"
                run.status = RunStatus.PAUSED
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))

                task = PendingTask(
                    workspaceId=run.workspaceId,
                    runId=run.runId,
                    nodeId=node.id,
                    title=node.config.title or "approval required",
                    content=run.contextSandbox.model_dump(),
                )
                await self.store.save_task(task.taskId, run.workspaceId, run.runId, task.model_dump(mode="json"))
                logger.info("run paused at approval gate: %s node %s task %s", run.runId, node.id, task.taskId)

                await self._push_approval_notification(run, task)

            elif node.type == NodeType.OUTPUT_NODE:
                output_key = node.config.outputKey or "output"
                run.contextSandbox.artifacts.append({
                    "key": output_key,
                    "nodeId": node.id,
                    "data": run.contextSandbox.inputData,
                })
                trace.status = "success"
                trace.output = {"outputKey": output_key}
                trace.exitTime = utc_now()
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
                await self._create_artifact_for_output(run, node, output_key)
                await self._archive_output_to_rag(run, node, output_key)
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.END_NODE:
                trace.status = "success"
                trace.output = {}
                trace.exitTime = utc_now()
                await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))

        except Exception as e:
            logger.error("node execution failed: %s run %s error %s", node.id, run.runId, e)
            trace.status = "failed"
            trace.errorMsg = str(e)
            trace.exitTime = utc_now()
            run.status = RunStatus.FAILED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))

    def _find_node(self, graph: GraphDefinition, node_id: str) -> WorkflowNode | None:
        for n in graph.nodes:
            if n.id == node_id:
                return n
        return None

    def _get_next_nodes(
        self, graph: GraphDefinition, node_id: str, condition: str | None = None
    ) -> list[WorkflowNode]:
        edges = graph.edges
        next_ids = []
        for e in edges:
            if e.source == node_id:
                if condition and e.condition:
                    if e.condition == condition:
                        next_ids.append(e.target)
                elif not e.condition and condition is None:
                    next_ids.append(e.target)
        result = []
        for nid in next_ids:
            node = self._find_node(graph, nid)
            if node:
                result.append(node)
        return result

    def _find_or_create_trace(self, run: RunInstance, node_id: str) -> NodeTrace:
        for t in run.nodeTrace:
            if t.nodeId == node_id:
                return t
        trace = NodeTrace(nodeId=node_id)
        run.nodeTrace.append(trace)
        return trace

    def _build_node_input(self, run: RunInstance, node: WorkflowNode) -> dict:
        if node.type == NodeType.CONNECTOR_NODE:
            return {
                "connectorId": node.config.connectorId,
                "action": node.config.action,
                "contextData": run.contextSandbox.inputData,
            }
        elif node.type == NodeType.SKILL_NODE:
            return {
                "skillId": node.config.skillId,
                "contextData": run.contextSandbox.inputData,
                "variables": run.contextSandbox.variables,
            }
        return {}

    async def _create_artifact_for_output(self, run: RunInstance, node: WorkflowNode, output_key: str):
        try:
            from .artifact_client import create_external_artifact
            extra = node.config.extra if node.config else {}
            await create_external_artifact(
                source_module="fsb",
                workspace_id=run.workspaceId,
                name=extra.get("artifactName", f"output_{output_key}"),
                artifact_type=extra.get("artifactType", "text"),
                content=str(run.contextSandbox.inputData),
                workflow_run_id=run.runId,
                project_id=extra.get("projectId"),
                metadata={"outputKey": output_key, "nodeId": node.id},
            )
        except Exception as e:
            logger.warning("artifact creation skipped: run=%s node=%s error=%s", run.runId, node.id, e)

    async def _archive_output_to_rag(self, run: RunInstance, node: WorkflowNode, output_key: str):
        try:
            from .rag_client import upload_document
            extra = node.config.extra if node.config else {}
            kb_id = extra.get("knowledgeBaseId", "")
            if not kb_id:
                logger.debug("no knowledgeBaseId configured for output node, skip rag archive")
                return
            import json
            import os
            import tempfile
            content = json.dumps(run.contextSandbox.inputData, ensure_ascii=False, indent=2)
            tmp_dir = tempfile.mkdtemp(prefix="fsb_rag_")
            tmp_path = os.path.join(tmp_dir, f"{output_key}_{run.runId[:8]}.json")
            with open(tmp_path, "w") as f:
                f.write(content)
            result = await upload_document(kb_id=kb_id, file_path=tmp_path, contextualize=True)
            if result.get("success"):
                logger.info("output archived to rag: kb=%s doc=%s", kb_id, result["data"].get("doc_id"))
            else:
                logger.warning("rag archive failed: kb=%s error=%s", kb_id, result.get("message"))
        except Exception as e:
            logger.warning("rag archive skipped: run=%s node=%s error=%s", run.runId, node.id, e)

    async def _push_approval_notification(self, run: RunInstance, task: PendingTask):
        try:
            from .cowork_client import push_notification
            await push_notification(
                space_id=run.workspaceId,
                user_id="admin",
                notification_type="approval",
                title=task.title,
                content=f"Run {run.runId} requires approval",
                metadata={"runId": run.runId, "taskId": task.taskId, "nodeId": task.nodeId},
            )
        except Exception as e:
            logger.warning("approval notification skipped: run=%s task=%s error=%s", run.runId, task.taskId, e)

    async def _execute_connector(self, run: RunInstance, node: WorkflowNode) -> dict:
        connector_id = node.config.connectorId
        action = node.config.action or ""
        logger.info("connector execution: %s action=%s", connector_id, action)

        try:
            from .gateway_client import execute_action
            conn_data = await self.store.get_connector(
                f"{run.workspaceId}_{connector_id}"
            )
            connection_id = ""
            if conn_data:
                connection_id = conn_data.get("data", {}).get("connectionId", "")

            result = await execute_action(
                connector_key=connector_id,
                action_key=action,
                params=run.contextSandbox.inputData,
                connection_id=connection_id,
            )
            if result.get("success"):
                logger.info("connector executed via gateway: %s/%s", connector_id, action)
                return {
                    "connectorId": connector_id,
                    "action": action,
                    "status": "success",
                    "data": result,
                }
            logger.warning("connector gateway call failed, fallback to stub: %s error=%s", connector_id, result.get("message"))
        except Exception as e:
            logger.warning("connector gateway error, fallback to stub: %s error=%s", connector_id, e)

        return {
            "connectorId": connector_id,
            "action": action,
            "status": "simulated",
            "data": {"message": f"connector {connector_id}/{action} simulated (stub mode)"},
        }

    async def _execute_skill(self, run: RunInstance, node: WorkflowNode) -> dict:
        skill_data = await self.store.get_skill(node.config.skillId)
        if skill_data:
            skill_name = skill_data.get("name", "unknown")
            skill_type = skill_data.get("type", "prompt")
            skill_definition = skill_data.get("definition", "")
        else:
            skill_name = node.config.skillId
            skill_type = "prompt"
            skill_definition = ""

        if skill_type == "prompt" and skill_definition:
            try:
                from .llm_client import execute_skill_prompt
                result = await execute_skill_prompt(
                    skill_definition=skill_definition,
                    input_data=run.contextSandbox.inputData,
                    variables=run.contextSandbox.variables,
                    model=node.config.extra.get("model", ""),
                )
                if result.get("status") == "success":
                    logger.info("skill executed via LLM: %s", skill_name)
                    return {
                        "skillId": node.config.skillId,
                        "skillName": skill_name,
                        "status": "success",
                        "data": result,
                    }
                logger.warning("skill LLM call failed, fallback to stub: %s error=%s", skill_name, result.get("message"))
            except Exception as e:
                logger.warning("skill LLM call error, fallback to stub: %s error=%s", skill_name, e)

        logger.info("skill execution (stub): %s", skill_name)
        return {
            "skillId": node.config.skillId,
            "skillName": skill_name,
            "status": "simulated",
            "data": {"message": f"skill {skill_name} executed (stub mode)"},
        }

    async def _execute_condition(self, run: RunInstance, node: WorkflowNode) -> dict:
        expr = node.config.conditionExpr or "default"
        logger.info("condition evaluation (stub): %s", expr)
        return {"branch": "default", "expr": expr}

    async def _dispatch_webhooks(self, run: RunInstance):
        event = f"run.{run.status.value.lower()}"
        try:
            hooks = await self.store.find_webhooks_for_event(run.workspaceId, event)
            if not hooks:
                return
            from .webhook_dispatcher import dispatch_webhook
            for hook in hooks:
                await dispatch_webhook(hook, event, run.model_dump(mode="json"))
        except Exception as e:
            logger.error("webhook dispatch error: run=%s error=%s", run.runId, e)
