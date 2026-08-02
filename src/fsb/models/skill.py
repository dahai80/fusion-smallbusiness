import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .common import ActionSchema, SkillType, gen_id, utc_now

logger = logging.getLogger(__name__)


class SkillCreate(BaseModel):
    name: str
    displayName: str = ""
    type: SkillType = SkillType.PROMPT
    definition: str = ""
    inputSchema: ActionSchema = Field(default_factory=ActionSchema)
    outputFormat: str = "json"
    enabled: bool = True


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    displayName: Optional[str] = None
    definition: Optional[str] = None
    inputSchema: Optional[ActionSchema] = None
    outputFormat: Optional[str] = None
    enabled: Optional[bool] = None


class Skill(BaseModel):
    skillId: str = Field(default_factory=lambda: gen_id("skill"))
    workspaceId: str = ""
    name: str
    displayName: str = ""
    type: SkillType = SkillType.PROMPT
    definition: str = ""
    inputSchema: ActionSchema = Field(default_factory=ActionSchema)
    outputFormat: str = "json"
    enabled: bool = True
    createTime: datetime = Field(default_factory=utc_now)
