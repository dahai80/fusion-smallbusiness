import logging

from ..db.store import MAX_PAGE, Store
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

        try:
            self._validate_graph(wf.graphDefinition)
        except ValueError as e:
            run.status = RunStatus.FAILED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
            logger.error("resume aborted: graph validation failed run=%s error=%s", run_id, e)
            raise

        current_node = self._find_node(wf.graphDefinition, run.currentNodeId)
        if not current_node or current_node.type != NodeType.APPROVAL_GATE_NODE:
            run.status = RunStatus.FAILED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
            logger.error("resume aborted: currentNodeId=%s not an approval gate run=%s", run.currentNodeId, run_id)
            raise ValueError(f"resume point {run.currentNodeId} is no longer an approval gate (workflow edited?)")

        run.status = RunStatus.RUNNING
        updated = await self.store.cas_run_status(
            run.runId,
            run.workspaceId,
            run.workflowId,
            run.model_dump(mode="json"),
            expected_status=RunStatus.PAUSED.value,
        )
        if not updated:
            logger.warning("resume lost CAS race: run=%s already resumed by concurrent caller", run_id)
            return

        trace = self._find_or_create_trace(run, current_node.id)
        trace.exitTime = utc_now()
        trace.status = f"paused_then_{decision}"
        trace.output = {"action": decision}

        next_nodes = self._get_next_nodes(wf.graphDefinition, run.currentNodeId, decision)
        for node in next_nodes:
            if run.status != RunStatus.RUNNING:
                break
            await self._execute_node(run, node, wf.graphDefinition)

        if run.status == RunStatus.RUNNING:
            run.status = RunStatus.COMPLETED
            run.endTime = utc_now()
            await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
            logger.info("run completed after resume: %s", run_id)
            await self._dispatch_webhooks(run)
            await self._notify_chat(run)

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
            n for n in graph.nodes if n.type == NodeType.CONNECTOR_NODE and n.config and self._is_write_node(n)
        ]
        for wn in write_nodes:
            has_gate_upstream = self._has_approval_gate_upstream(graph, wn.id)
            if not has_gate_upstream:
                raise ValueError(f"write connector node {wn.id} must have approval gate upstream")

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

        dangling = [n.id for n in graph.nodes if n.id not in reachable_to_end and n.type != NodeType.END_NODE]
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
            await self._notify_chat(run)

    async def _execute_node(self, run: RunInstance, node: WorkflowNode, graph: GraphDefinition):
        if run.status != RunStatus.RUNNING:
            logger.info("skip node %s: run %s status=%s (early stop)", node.id, run.runId, run.status)
            return
        logger.info("executing node: %s type=%s run=%s", node.id, node.type, run.runId)
        trace = NodeTrace(nodeId=node.id, input=self._build_node_input(run, node))
        run.nodeTrace.append(trace)
        run.currentNodeId = node.id

        try:
            if node.type == NodeType.START_NODE:
                trace.status = "success"
                trace.output = {}
                trace.exitTime = utc_now()
                await self._checkpoint(run, trace)
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    if run.status != RunStatus.RUNNING:
                        break
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.CONNECTOR_NODE:
                result = await self._execute_connector(run, node)
                trace.status = result.get("status", "success")
                trace.output = result
                trace.exitTime = utc_now()
                run.contextSandbox.snapshots[node.config.connectorId] = result
                await self._checkpoint(run, trace)
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    if run.status != RunStatus.RUNNING:
                        break
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.SKILL_NODE:
                result = await self._execute_skill(run, node)
                trace.status = result.get("status", "success")
                trace.output = result
                trace.exitTime = utc_now()
                await self._checkpoint(run, trace)
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    if run.status != RunStatus.RUNNING:
                        break
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.CONDITION_NODE:
                result = await self._execute_condition(run, node, graph)
                trace.status = "success"
                trace.output = result
                trace.exitTime = utc_now()
                await self._checkpoint(run, trace)
                branch = result.get("branch", "default")
                next_nodes = self._get_next_nodes(graph, node.id, branch)
                for n in next_nodes:
                    if run.status != RunStatus.RUNNING:
                        break
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.APPROVAL_GATE_NODE:
                trace.status = "paused"
                run.status = RunStatus.PAUSED
                await self._checkpoint(run, trace)

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
                run.contextSandbox.artifacts.append(
                    {
                        "key": output_key,
                        "nodeId": node.id,
                        "data": run.contextSandbox.inputData,
                    }
                )
                trace.status = "success"
                trace.output = {"outputKey": output_key}
                trace.exitTime = utc_now()
                await self._checkpoint(run, trace)
                await self._create_artifact_for_output(run, node, output_key)
                await self._archive_output_to_rag(run, node, output_key)
                next_nodes = self._get_next_nodes(graph, node.id)
                for n in next_nodes:
                    if run.status != RunStatus.RUNNING:
                        break
                    await self._execute_node(run, n, graph)

            elif node.type == NodeType.END_NODE:
                trace.status = "success"
                trace.output = {}
                trace.exitTime = utc_now()
                await self._checkpoint(run, trace)

        except Exception as e:
            logger.error("node execution failed: %s run %s error %s", node.id, run.runId, e)
            trace.status = "failed"
            trace.errorMsg = str(e)
            trace.exitTime = utc_now()
            run.status = RunStatus.FAILED
            run.endTime = utc_now()
            await self._checkpoint(run, trace)

    def _find_node(self, graph: GraphDefinition, node_id: str) -> WorkflowNode | None:
        for n in graph.nodes:
            if n.id == node_id:
                return n
        return None

    async def _checkpoint(self, run: RunInstance, trace: NodeTrace):
        await self.store.save_run(run.runId, run.workspaceId, run.workflowId, run.model_dump(mode="json"))
        seq = len(run.nodeTrace) - 1
        try:
            await self.store.append_run_trace(run.runId, seq, trace.model_dump(mode="json"))
        except Exception as e:
            logger.warning("append_run_trace failed run=%s seq=%d: %s", run.runId, seq, e)

    def _get_next_nodes(self, graph: GraphDefinition, node_id: str, condition: str | None = None) -> list[WorkflowNode]:
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
        import json
        import os
        import shutil
        import tempfile

        tmp_dir = None
        try:
            from .rag_client import upload_document

            extra = node.config.extra if node.config else {}
            kb_id = extra.get("knowledgeBaseId", "")
            if not kb_id:
                logger.debug("no knowledgeBaseId configured for output node, skip rag archive")
                return
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
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.debug("rag temp dir cleaned: %s", tmp_dir)

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

    async def _resolve_connector(self, ws_id: str, connector_key: str) -> dict | None:
        try:
            connectors = await self.store.list_connectors(ws_id, offset=0, limit=MAX_PAGE)
        except Exception as e:
            logger.warning("list_connectors failed ws=%s: %s", ws_id, e)
            return None
        for c in connectors:
            if c.get("connectorKey") == connector_key:
                return c
        logger.warning("no connector found for key=%s ws=%s", connector_key, ws_id)
        return None

    async def _execute_connector(self, run: RunInstance, node: WorkflowNode) -> dict:
        connector_id = node.config.connectorId
        action = node.config.action or ""
        logger.info("connector execution: %s action=%s", connector_id, action)

        try:
            from .gateway_client import execute_action

            conn_data = await self._resolve_connector(run.workspaceId, connector_id)
            connection_id = ""
            if conn_data:
                connection_id = conn_data.get("connectionId", "")
            if connection_id:
                logger.info("connector resolved: %s connectionId=%s", connector_id, connection_id)
            else:
                logger.warning("connector has no connectionId: %s ws=%s", connector_id, run.workspaceId)

            interp_params = self._interpolate_dict(
                run.contextSandbox.inputData, run.contextSandbox.variables, run.contextSandbox.inputData
            )
            result = await execute_action(
                connector_key=connector_id,
                action_key=action,
                params=interp_params,
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
            logger.warning(
                "connector gateway call failed, fallback to stub: %s error=%s", connector_id, result.get("message")
            )
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
            result = await self._execute_prompt_skill(run, node, skill_name, skill_definition)
            if result is not None:
                return result

        if skill_type == "api_call":
            result = await self._execute_api_call_skill(run, node, skill_name, skill_data or {})
            if result is not None:
                return result

        if skill_type == "function":
            result = await self._execute_function_skill(run, node, skill_name, skill_definition)
            if result is not None:
                return result

        logger.info("skill execution (stub): %s", skill_name)
        return {
            "skillId": node.config.skillId,
            "skillName": skill_name,
            "status": "simulated",
            "data": {"message": f"skill {skill_name} executed (stub mode)"},
        }

    async def _execute_prompt_skill(
        self, run: RunInstance, node: WorkflowNode, skill_name: str, skill_definition: str
    ) -> dict | None:
        if not skill_definition:
            return None
        try:
            from .llm_client import execute_skill_prompt

            interp_def = self._interpolate_str(
                skill_definition, run.contextSandbox.variables, run.contextSandbox.inputData
            )
            result = await execute_skill_prompt(
                skill_definition=interp_def,
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
        return None

    async def _execute_api_call_skill(
        self, run: RunInstance, node: WorkflowNode, skill_name: str, skill_data: dict
    ) -> dict | None:
        api_cfg = skill_data.get("apiConfig") or {}
        url = api_cfg.get("url", "")
        if not url:
            logger.warning("api_call skill %s has no url, fallback to stub", skill_name)
            return None
        from .url_guard import resolve_pinned_url, validate_outbound_url

        ok, reason = validate_outbound_url(url)
        if not ok:
            logger.warning("api_call skill %s url rejected (ssrf guard): %s url=%s", skill_name, reason, url)
            return {
                "skillId": node.config.skillId,
                "skillName": skill_name,
                "status": "error",
                "data": {"message": f"url not allowed: {reason}"},
            }
        pinned_url, original_host = resolve_pinned_url(url)
        if not pinned_url:
            logger.warning("api_call skill %s url rejected (ssrf pin failed): %s", skill_name, url)
            return {
                "skillId": node.config.skillId,
                "skillName": skill_name,
                "status": "error",
                "data": {"message": "url not allowed: ssrf ip pin failed"},
            }
        method = (api_cfg.get("method") or "GET").upper()
        headers = dict(api_cfg.get("headers", {}))
        if original_host:
            headers.setdefault("Host", original_host)
        body_template = api_cfg.get("bodyTemplate", "")
        try:
            from .http_pool import acquire_client

            body = None
            if body_template:
                body = self._interpolate_str(body_template, run.contextSandbox.variables, run.contextSandbox.inputData)
            async with acquire_client(30.0) as client:
                resp = await client.request(
                    method, pinned_url, headers=headers, json=body if body else None, timeout=30.0
                )
                logger.info("api_call skill executed: %s %s -> %s", method, url, resp.status_code)
                try:
                    payload = resp.json()
                except Exception:
                    payload = resp.text
                safe_body = payload if resp.status_code < 300 else f"<response status={resp.status_code} body withheld>"
                return {
                    "skillId": node.config.skillId,
                    "skillName": skill_name,
                    "status": "success",
                    "data": {"status_code": resp.status_code, "body": safe_body},
                }
        except Exception as e:
            logger.warning("api_call skill error, fallback to stub: %s error=%s", skill_name, e)
            return None

    async def _execute_function_skill(
        self, run: RunInstance, node: WorkflowNode, skill_name: str, skill_definition: str
    ) -> dict | None:
        logger.info("function skill %s has no runtime registry, fallback to stub", skill_name)
        return None

    def _interpolate_str(self, text: str, variables: dict, input_data: dict) -> str:
        if not text or "${" not in text:
            return text
        ctx = {**variables, **input_data}
        import re

        def _repl(m):
            key = m.group(1).strip()
            val = ctx.get(key, "")
            return str(val)

        return re.sub(r"\$\{([^}]+)\}", _repl, text)

    def _interpolate_dict(self, params: dict, variables: dict, input_data: dict | None = None) -> dict:
        if not params:
            return params or {}
        input_data = input_data or {}
        out = {}
        for k, v in params.items():
            if isinstance(v, str):
                out[k] = self._interpolate_str(v, variables, input_data)
            elif isinstance(v, dict):
                out[k] = self._interpolate_dict(v, variables, input_data)
            elif isinstance(v, list):
                out[k] = [self._interpolate_str(it, variables, input_data) if isinstance(it, str) else it for it in v]
            else:
                out[k] = v
        return out

    async def _execute_condition(self, run: RunInstance, node: WorkflowNode, graph: GraphDefinition) -> dict:
        expr = node.config.conditionExpr or ""
        ctx = {
            **run.contextSandbox.variables,
            **run.contextSandbox.inputData,
        }
        from .expr import evaluate_condition

        matched = evaluate_condition(expr, ctx)
        non_default = [
            e.condition for e in graph.edges if e.source == node.id and e.condition and e.condition != "default"
        ]
        if len(non_default) > 1:
            logger.warning(
                "condition node %s has %d non-default branches %s — only first matched branch taken, "
                "multi-branch dispatch not supported (binary semantics)",
                node.id,
                len(non_default),
                non_default,
            )
        true_branch = non_default[0] if non_default else "true"
        branch = true_branch if matched else "default"
        logger.info("condition eval: expr=%r matched=%s branch=%s", expr, matched, branch)
        return {"branch": branch, "expr": expr, "matched": matched}

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

    async def _notify_chat(self, run: RunInstance):
        try:
            ws_data = await self.store.get_workspace(run.workspaceId)
            if not ws_data:
                return
            agent_id = ws_data.get("bindAgentId") if isinstance(ws_data, dict) else ""
            if not agent_id:
                return
            from .chat_client import notify_run_completed

            await notify_run_completed(run.workspaceId, agent_id, run.model_dump(mode="json"))
        except Exception as e:
            logger.warning("chat notify hook error: run=%s error=%s", run.runId, e)
