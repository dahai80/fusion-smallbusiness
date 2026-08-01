import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import Variable, gen_id, utc_now

logger = logging.getLogger(__name__)


class WorkspaceCreate(BaseModel):
    title: str
    description: str = ""
    projectId: Optional[str] = None
    bindAgentId: Optional[str] = None
    variables: list[Variable] = Field(default_factory=list)


class WorkspaceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    projectId: Optional[str] = None
    bindAgentId: Optional[str] = None


class Workspace(BaseModel):
    wsId: str = Field(default_factory=lambda: gen_id("fsb_ws"))
    title: str
    description: str = ""
    ownerUserId: str = ""
    projectId: Optional[str] = None
    bindAgentId: Optional[str] = None
    variables: list[Variable] = Field(default_factory=list)
    connectorIds: list[str] = Field(default_factory=list)
    skillIds: list[str] = Field(default_factory=list)
    workflowIds: list[str] = Field(default_factory=list)
    createTime: datetime = Field(default_factory=utc_now)
    updateTime: datetime = Field(default_factory=utc_now)
