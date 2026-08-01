import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import NodeType, ScheduleType, gen_id, utc_now

logger = logging.getLogger(__name__)


class NodeConfig(BaseModel):
    connectorId: Optional[str] = None
    action: Optional[str] = None
    permission: Optional[str] = None
    skillId: Optional[str] = None
    title: Optional[str] = None
    conditionExpr: Optional[str] = None
    outputKey: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    config: NodeConfig = Field(default_factory=NodeConfig)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: Optional[str] = None


class GraphDefinition(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entryNode: str = "n_start"


class ScheduleConfig(BaseModel):
    type: ScheduleType = ScheduleType.MANUAL
    cron: Optional[str] = None
    eventTrigger: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    slashCommand: Optional[str] = None
    displayName: str = ""
    description: str = ""
    version: str = "1.0"
    enabled: bool = True
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    graphDefinition: GraphDefinition = Field(default_factory=GraphDefinition)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    slashCommand: Optional[str] = None
    displayName: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    enabled: Optional[bool] = None
    schedule: Optional[ScheduleConfig] = None
    graphDefinition: Optional[GraphDefinition] = None


class Workflow(BaseModel):
    wfId: str = Field(default_factory=lambda: gen_id("wf"))
    workspaceId: str = ""
    name: str
    slashCommand: Optional[str] = None
    displayName: str = ""
    description: str = ""
    version: str = "1.0"
    enabled: bool = True
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    graphDefinition: GraphDefinition = Field(default_factory=GraphDefinition)
    createTime: datetime = Field(default_factory=utc_now)
    updateTime: datetime = Field(default_factory=utc_now)
