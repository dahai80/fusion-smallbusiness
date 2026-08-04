import logging

from fastapi import APIRouter, HTTPException

from ..db.store import Store
from ..models.skill import Skill, SkillCreate, SkillUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace/{wsId}/skill", tags=["skill"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


@router.get("", response_model=list[Skill])
async def list_skills(wsId: str, offset: int = 0, limit: int = 100):
    store = get_store()
    items = await store.list_skills(wsId, offset=offset, limit=limit)
    return [Skill(**d) for d in items]


@router.get("/{skillId}", response_model=Skill)
async def get_skill(wsId: str, skillId: str):
    store = get_store()
    data = await store.get_skill(skillId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="skill not found")
    return Skill(**data)


@router.post("", response_model=Skill)
async def create_skill(wsId: str, body: SkillCreate):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    sk = Skill(workspaceId=wsId, **body.model_dump())
    await store.save_skill(sk.skillId, wsId, sk.model_dump(mode="json"))
    ws["skillIds"] = list(set([*ws.get("skillIds", []), sk.skillId]))
    await store.save_workspace(wsId, ws)
    logger.info("skill created: %s in ws %s", sk.skillId, wsId)
    return sk


@router.put("/{skillId}", response_model=Skill)
async def update_skill(wsId: str, skillId: str, body: SkillUpdate):
    store = get_store()
    data = await store.get_skill(skillId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="skill not found")
    sk = Skill(**data)
    update = body.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(sk, k, v)
    await store.save_skill(sk.skillId, wsId, sk.model_dump(mode="json"))
    logger.info("skill updated: %s", skillId)
    return sk


@router.delete("/{skillId}")
async def delete_skill(wsId: str, skillId: str):
    store = get_store()
    data = await store.get_skill(skillId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="skill not found")
    await store.delete_skill(skillId)
    ws = await store.get_workspace(wsId)
    if ws:
        ws["skillIds"] = [s for s in ws.get("skillIds", []) if s != skillId]
        await store.save_workspace(wsId, ws)
    logger.info("skill deleted: %s", skillId)
    return {"success": True}


@router.post("/{skillId}/test")
async def test_skill(wsId: str, skillId: str, body: dict | None = None):
    store = get_store()
    data = await store.get_skill(skillId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="skill not found")
    logger.info("skill tested: %s (dry run)", skillId)
    return {
        "skillId": skillId,
        "dryRun": True,
        "message": "skill test executed (no LLM call)",
        "input": body or {},
    }
