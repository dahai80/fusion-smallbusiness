import logging
from datetime import datetime

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
    name: str | None = None
    displayName: str | None = None
    definition: str | None = None
    inputSchema: ActionSchema | None = None
    outputFormat: str | None = None
    enabled: bool | None = None


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
