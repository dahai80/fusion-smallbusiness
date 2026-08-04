import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class NodeType(StrEnum):
    START_NODE = "START_NODE"
    CONNECTOR_NODE = "CONNECTOR_NODE"
    SKILL_NODE = "SKILL_NODE"
    CONDITION_NODE = "CONDITION_NODE"
    APPROVAL_GATE_NODE = "APPROVAL_GATE_NODE"
    OUTPUT_NODE = "OUTPUT_NODE"
    END_NODE = "END_NODE"


class RunStatus(StrEnum):
    COMPLETED = "COMPLETED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"


class TriggerType(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EXTERNAL_API = "external_api"
    EVENT = "event"


class AuthType(StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"


class AuthStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"
    ERROR = "error"


class SkillType(StrEnum):
    PROMPT = "prompt"
    FUNCTION = "function"
    API_CALL = "api_call"


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    EDIT = "edit"


class ScheduleType(StrEnum):
    MANUAL = "manual"
    CRON = "cron"
    EVENT = "event"


class ConnectorPermission(StrEnum):
    READ = "read"
    WRITE = "write"


class Variable(BaseModel):
    key: str
    value: Any
    description: str | None = None


class ApiCallConfig(BaseModel):
    url: str = ""
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    bodyTemplate: str = ""


class ActionSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)


class ConnectorActionMeta(BaseModel):
    actionKey: str
    displayName: str
    permission: ConnectorPermission = ConnectorPermission.READ
    inputSchema: ActionSchema = Field(default_factory=ActionSchema)
    outputSchema: ActionSchema = Field(default_factory=ActionSchema)


class ConnectorMeta(BaseModel):
    connectorKey: str
    displayName: str
    icon: str = ""
    authType: AuthType = AuthType.OAUTH2
    description: str = ""
    readOnlyRecommend: bool = True
    actions: list[ConnectorActionMeta] = Field(default_factory=list)
