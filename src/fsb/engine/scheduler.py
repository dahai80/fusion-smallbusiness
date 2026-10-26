import contextlib
import logging
import os
import socket

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import fsb_config
from ..db.store import Store
from ..models.common import ScheduleType, TriggerType
from ..models.workflow import Workflow

logger = logging.getLogger(__name__)


def _default_holder() -> str:
    return f"fsb:{socket.gethostname()}:{os.getpid()}"


class WorkflowScheduler:
    def __init__(self, store: Store, holder: str | None = None):
        self.store = store
        self.holder = holder or _default_holder()
        self._scheduler = AsyncIOScheduler()
        self._jobs: dict[str, str] = {}
        self._leader_ttl = max(5, fsb_config.SCHEDULER_LEADER_TTL)
        self._leader_renewal_job = None

    def start(self):
        self._scheduler.start()
        logger.info("scheduler started (holder=%s)", self.holder)

    def stop(self):
        if self._leader_renewal_job:
            with contextlib.suppress(Exception):
                self._scheduler.remove_job(self._leader_renewal_job)
            self._leader_renewal_job = None
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")

    async def _renew_leadership(self):
        try:
            ok = await self.store.renew_leader(self.holder, self._leader_ttl)
            if not ok:
                logger.info("leadership lost, attempting re-acquire (holder=%s)", self.holder)
                await self.store.try_acquire_leader(self.holder, self._leader_ttl)
        except Exception as e:
            logger.warning("leader renewal failed: %s", e)

    async def ensure_leadership(self) -> bool:
        try:
            acquired = await self.store.try_acquire_leader(self.holder, self._leader_ttl)
            if acquired and self._leader_renewal_job is None:
                renew_interval = max(2, self._leader_ttl // 3)
                self._leader_renewal_job = self._scheduler.add_job(
                    self._renew_leadership,
                    "interval",
                    seconds=renew_interval,
                    id="fsb_leader_renewal",
                    replace_existing=True,
                ).id
                logger.info("leadership acquired (holder=%s ttl=%ds)", self.holder, self._leader_ttl)
            return acquired
        except Exception as e:
            logger.warning("leader acquire failed: %s", e)
            return False

    async def is_leader(self) -> bool:
        try:
            return await self.store.is_leader(self.holder)
        except Exception as e:
            logger.warning("is_leader check failed: %s", e)
            return False

    async def register(self, ws_id: str, wf_id: str):
        data = await self.store.get_workflow(wf_id)
        if not data:
            logger.warning("cannot register schedule: wf %s not found", wf_id)
            return
        wf = Workflow(**data)
        if wf.schedule.type != ScheduleType.CRON or not wf.schedule.cron:
            logger.info("skipping non-cron schedule: wf %s", wf_id)
            return
        job_id = f"fsb_{ws_id}_{wf_id}"
        if job_id in self._jobs:
            self._scheduler.remove_job(job_id)
        try:
            parts = wf.schedule.cron.split()
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]
                )
            else:
                logger.warning("invalid cron format: %s", wf.schedule.cron)
                return
            self._scheduler.add_job(
                self._run_scheduled_workflow,
                trigger=trigger,
                id=job_id,
                args=[ws_id, wf_id],
                replace_existing=True,
            )
            self._jobs[job_id] = wf_id
            logger.info("cron registered: wf %s cron=%s", wf_id, wf.schedule.cron)
        except Exception as e:
            logger.error("failed to register cron for wf %s: %s", wf_id, e)

    async def unregister(self, ws_id: str, wf_id: str):
        job_id = f"fsb_{ws_id}_{wf_id}"
        if job_id in self._jobs:
            self._scheduler.remove_job(job_id)
            del self._jobs[job_id]
            logger.info("cron unregistered: wf %s", wf_id)

    async def _run_scheduled_workflow(self, ws_id: str, wf_id: str):
        if not await self.is_leader():
            logger.debug("non-leader skipping scheduled run: ws %s wf %s (holder=%s)", ws_id, wf_id, self.holder)
            return
        logger.info("scheduled run triggered: ws %s wf %s", ws_id, wf_id)
        from .runner import WorkflowRunner

        runner = WorkflowRunner(self.store)
        try:
            run = await runner.start(
                ws_id,
                wf_id,
                trigger_type=TriggerType.SCHEDULE,
                triggered_by="scheduler",
            )
            logger.info("scheduled run completed: %s", run.runId)
        except Exception as e:
            logger.error("scheduled run failed: ws %s wf %s error %s", ws_id, wf_id, e)

    def list_jobs(self) -> list[dict]:
        result = []
        for job_id, wf_id in self._jobs.items():
            result.append({"jobId": job_id, "wfId": wf_id})
        return result
