import logging
from typing import Optional
from difflib import SequenceMatcher

from ..db.store import Store
from ..models.workflow import Workflow

logger = logging.getLogger(__name__)


class IntentRouter:
    def __init__(self, store: Store):
        self.store = store

    async def match(self, ws_id: str, query: str) -> Optional[Workflow]:
        query = query.strip()
        if query.startswith("/"):
            return await self._match_slash(ws_id, query)
        return await self._match_natural(ws_id, query)

    async def _match_slash(self, ws_id: str, command: str) -> Optional[Workflow]:
        items = await self.store.list_workflows(ws_id)
        for d in items:
            wf = Workflow(**d)
            if wf.slashCommand and wf.slashCommand == command and wf.enabled:
                logger.info("slash match: %s -> %s", command, wf.wfId)
                return wf
        logger.info("no slash match for: %s", command)
        return None

    async def _match_natural(self, ws_id: str, query: str) -> Optional[Workflow]:
        items = await self.store.list_workflows(ws_id)
        best_wf = None
        best_score = 0.0
        query_lower = query.lower()
        for d in items:
            wf = Workflow(**d)
            if not wf.enabled:
                continue
            score = 0.0
            if wf.slashCommand and wf.slashCommand.lower() in query_lower:
                score = 0.9
            if wf.name:
                score = max(score, SequenceMatcher(None, query_lower, wf.name.lower()).ratio())
            if wf.displayName:
                score = max(score, SequenceMatcher(None, query_lower, wf.displayName.lower()).ratio())
            if wf.description:
                score = max(score, SequenceMatcher(None, query_lower, wf.description.lower()).ratio() * 0.8)
            if score > best_score:
                best_score = score
                best_wf = wf
        threshold = 0.4
        if best_wf and best_score >= threshold:
            logger.info("natural match: '%s' -> %s score=%.2f", query, best_wf.wfId, best_score)
            return best_wf
        logger.info("no natural match for: '%s' (best=%.2f)", query, best_score)
        return None

    async def list_slash_commands(self, ws_id: str) -> list[dict]:
        items = await self.store.list_workflows(ws_id)
        result = []
        for d in items:
            wf = Workflow(**d)
            if wf.slashCommand and wf.enabled:
                result.append({
                    "slashCommand": wf.slashCommand,
                    "wfId": wf.wfId,
                    "name": wf.name,
                    "displayName": wf.displayName,
                })
        return result
