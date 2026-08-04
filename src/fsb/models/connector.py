import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import AuthStatus, AuthType, gen_id

logger = logging.getLogger(__name__)


class ConnectorCreate(BaseModel):
    connectorKey: str
    authType: AuthType = AuthType.OAUTH2
    authConfig: dict[str, Any] = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    authConfig: dict[str, Any] | None = None


class Connector(BaseModel):
    connId: str = Field(default_factory=lambda: gen_id("conn"))
    workspaceId: str
    connectorKey: str
    authType: AuthType = AuthType.OAUTH2
    authStatus: AuthStatus = AuthStatus.DISCONNECTED
    connectedAt: datetime | None = None
    tokenExpiryAt: datetime | None = None
    permissions: list[str] = Field(default_factory=list)
    lastRefreshAt: datetime | None = None
    authConfig: dict[str, Any] = Field(default_factory=dict)
