import logging
from datetime import datetime

from pydantic import BaseModel, Field

from .common import gen_id, utc_now

logger = logging.getLogger(__name__)


class Webhook(BaseModel):
    webhookId: str = Field(default_factory=lambda: gen_id("wh"))
    workspaceId: str
    url: str
    events: list[str] = Field(default_factory=lambda: ["run.completed"])
    secret: str = ""
    enabled: bool = True
    createTime: datetime = Field(default_factory=utc_now)
