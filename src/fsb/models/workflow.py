import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .common import NodeType, ScheduleType, gen_id, utc_now

logger = logging.getLogger(__name__)


class NodeConfig(BaseModel):
    connectorId: str | None = None
    action: str | None = None
    permission: str | None = None
    skillId: str | None = None
    label: str | None = None
    title: str | None = None
    conditionExpr: str | None = None
    outputKey: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    config: NodeConfig = Field(default_factory=NodeConfig)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: str | None = None


class GraphDefinition(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entryNode: str = ""

    @model_validator(mode="after")
    def _resolve_entry_node(self) -> "GraphDefinition":
        if not self.entryNode:
            for n in self.nodes:
                if n.type == NodeType.START_NODE:
                    self.entryNode = n.id
                    break
        return self


class ScheduleConfig(BaseModel):
    type: ScheduleType = ScheduleType.MANUAL
    cron: str | None = None
    eventTrigger: str | None = None


class WorkflowCreate(BaseModel):
    name: str
    slashCommand: str | None = None
    displayName: str = ""
    description: str = ""
    version: str = "1.0"
    enabled: bool = True
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    graphDefinition: GraphDefinition = Field(default_factory=GraphDefinition)


class WorkflowUpdate(BaseModel):
    name: str | None = None
    slashCommand: str | None = None
    displayName: str | None = None
    description: str | None = None
    version: str | None = None
    enabled: bool | None = None
    schedule: ScheduleConfig | None = None
    graphDefinition: GraphDefinition | None = None


class Workflow(BaseModel):
    wfId: str = Field(default_factory=lambda: gen_id("wf"))
    workspaceId: str = ""
    name: str
    slashCommand: str | None = None
    displayName: str = ""
    description: str = ""
    version: str = "1.0"
    enabled: bool = True
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    graphDefinition: GraphDefinition = Field(default_factory=GraphDefinition)
    createTime: datetime = Field(default_factory=utc_now)
    updateTime: datetime = Field(default_factory=utc_now)
