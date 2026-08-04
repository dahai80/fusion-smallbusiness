import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import gen_id, utc_now

logger = logging.getLogger(__name__)


class EventTrigger(BaseModel):
    eventId: str = Field(default_factory=lambda: gen_id("evt"))
    eventType: str
    source: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    workspaceId: str = ""
    createTime: datetime = Field(default_factory=utc_now)


class EventSubscription(BaseModel):
    subId: str = Field(default_factory=lambda: gen_id("sub"))
    workspaceId: str
    workflowId: str
    eventType: str
    source: str | None = None
    enabled: bool = True
    createTime: datetime = Field(default_factory=utc_now)
