import logging

from .connectors.registry import get_builtin_connectors
from .models.workspace import Workspace
from .skills.registry import get_builtin_skills
from .workflows.registry import get_builtin_workflows

logger = logging.getLogger(__name__)

BUILTIN_WS_ID = "fsb_ws_builtin"
BUILTIN_WS_TITLE = "Fusion Small Business Builtins"


async def _ensure_builtin_workspace(store) -> Workspace:
    ws_data = await store.get_workspace(BUILTIN_WS_ID)
    if ws_data:
        return Workspace(**ws_data)
    ws = Workspace(wsId=BUILTIN_WS_ID, title=BUILTIN_WS_TITLE, description="System builtin skills and workflows")
    await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
    logger.info("builtin workspace created: %s", ws.wsId)
    return ws


async def _seed_skills(store, ws: Workspace) -> list[str]:
    seeded = []
    existing = {s["skillId"] for s in await store.list_skills(ws.wsId, limit=1000)}
    for skill in get_builtin_skills():
        if skill.skillId in existing:
            continue
        skill.workspaceId = ws.wsId
        await store.save_skill(skill.skillId, ws.wsId, skill.model_dump(mode="json"))
        seeded.append(skill.skillId)
    if seeded:
        ws.skillIds = sorted(set(ws.skillIds) | set(seeded))
        await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
        logger.info("seeded %d builtin skills into %s", len(seeded), ws.wsId)
    return seeded


async def _seed_workflows(store, ws: Workspace) -> list[str]:
    seeded = []
    existing = {w["wfId"] for w in await store.list_workflows(ws.wsId, limit=1000)}
    for wf in get_builtin_workflows():
        stable_id = f"wf_builtin_{wf.name}"
        if stable_id in existing:
            continue
        wf.wfId = stable_id
        wf.workspaceId = ws.wsId
        await store.save_workflow(wf.wfId, ws.wsId, wf.model_dump(mode="json"))
        seeded.append(wf.wfId)
    if seeded:
        ws.workflowIds = sorted(set(ws.workflowIds) | set(seeded))
        await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
        logger.info("seeded %d builtin workflows into %s", len(seeded), ws.wsId)
    return seeded


async def seed_builtins(store) -> dict:
    ws = await _ensure_builtin_workspace(store)
    skills = await _seed_skills(store, ws)
    workflows = await _seed_workflows(store, ws)
    logger.info("builtin seeding done: skills=%d workflows=%d", len(skills), len(workflows))
    return {"workspaceId": ws.wsId, "skillsSeeded": len(skills), "workflowsSeeded": len(workflows)}


async def copy_builtins_to_workspace(store, ws_id: str) -> dict:
    ws_data = await store.get_workspace(ws_id)
    if not ws_data:
        raise ValueError(f"workspace not found: {ws_id}")
    ws = Workspace(**ws_data)
    skills = await _seed_skills(store, ws)
    workflows = await _seed_workflows(store, ws)
    logger.info("builtins copied into ws %s: skills=%d workflows=%d", ws_id, len(skills), len(workflows))
    return {"workspaceId": ws_id, "skillsSeeded": len(skills), "workflowsSeeded": len(workflows)}


def list_builtin_connector_meta() -> list[dict]:
    return [c.model_dump(mode="json") for c in get_builtin_connectors()]
