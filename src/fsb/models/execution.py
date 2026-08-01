import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import ApprovalAction, RunStatus, TriggerType, gen_id, utc_now

logger = logging.getLogger(__name__)


class NodeTrace(BaseModel):
    nodeId: str
    enterTime: datetime = Field(default_factory=utc_now)
    exitTime: Optional[datetime] = None
    status: str = "running"
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    errorMsg: str = ""


class ApprovalRecord(BaseModel):
    taskId: str = Field(default_factory=lambda: gen_id("task"))
    operateUser: str = ""
    action: ApprovalAction = ApprovalAction.APPROVE
    time: datetime = Field(default_factory=utc_now)
    editContent: Optional[dict[str, Any]] = None


class ContextSandbox(BaseModel):
    snapshots: dict[str, Any] = Field(default_factory=dict)
    inputData: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class RunInstance(BaseModel):
    runId: str = Field(default_factory=lambda: gen_id("run"))
    workspaceId: str = ""
    workflowId: str = ""
    triggerType: TriggerType = TriggerType.MANUAL
    triggeredBy: str = ""
    status: RunStatus = RunStatus.RUNNING
    contextSandbox: ContextSandbox = Field(default_factory=ContextSandbox)
    currentNodeId: Optional[str] = None
    startTime: datetime = Field(default_factory=utc_now)
    endTime: Optional[datetime] = None
    nodeTrace: list[NodeTrace] = Field(default_factory=list)
    approvalRecord: list[ApprovalRecord] = Field(default_factory=list)


class PendingTask(BaseModel):
    taskId: str = Field(default_factory=lambda: gen_id("task"))
    workspaceId: str = ""
    runId: str = ""
    nodeId: str = ""
    title: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    createTime: datetime = Field(default_factory=utc_now)
