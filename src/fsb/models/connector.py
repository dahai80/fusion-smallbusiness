import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import AuthStatus, AuthType, gen_id

logger = logging.getLogger(__name__)


class ConnectorCreate(BaseModel):
    connectorKey: str
    authType: AuthType = AuthType.OAUTH2
    authConfig: dict[str, Any] = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    authConfig: Optional[dict[str, Any]] = None


class Connector(BaseModel):
    connId: str = Field(default_factory=lambda: gen_id("conn"))
    workspaceId: str
    connectorKey: str
    authType: AuthType = AuthType.OAUTH2
    authStatus: AuthStatus = AuthStatus.DISCONNECTED
    connectedAt: Optional[datetime] = None
    tokenExpiryAt: Optional[datetime] = None
    permissions: list[str] = Field(default_factory=list)
    lastRefreshAt: Optional[datetime] = None
    authConfig: dict[str, Any] = Field(default_factory=dict)
