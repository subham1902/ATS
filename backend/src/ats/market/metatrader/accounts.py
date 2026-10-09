"""Account records contain references and observed state, never credentials."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class ConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class AccountMode(StrEnum):
    DEMO = "DEMO"
    LIVE = "LIVE"
    UNKNOWN = "UNKNOWN"


class AdoptAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=80)
    terminal_path: str = Field(min_length=1, max_length=512)
    broker_symbol: str = Field(default="XAUUSD", min_length=1, max_length=64)


class ConnectAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    platform: Literal["MT5", "MT4"] = "MT5"
    display_name: str = Field(min_length=1, max_length=80)
    broker: str = Field(default="", max_length=100)
    server: str = Field(min_length=1, max_length=100)
    login: SecretStr = Field(repr=False)
    password: SecretStr = Field(repr=False)
    terminal_path: str | None = Field(default=None, max_length=512)
    portable: bool = False
    broker_symbol: str = Field(default="XAUUSD", min_length=1, max_length=64)
    action: Literal["CONNECT_ONLY", "CONNECT_AND_ENABLE_EXECUTION"] = "CONNECT_ONLY"

    @model_validator(mode="after")
    def validate_connection(self) -> ConnectAccount:
        if not self.login.get_secret_value().isdigit() or int(self.login.get_secret_value()) <= 0:
            raise ValueError("LOGIN_MUST_BE_POSITIVE_INTEGER")
        if not self.password.get_secret_value():
            raise ValueError("PASSWORD_REQUIRED")
        if self.platform == "MT5" and not self.terminal_path:
            raise ValueError("ISOLATED_TERMINAL_PATH_REQUIRED")
        return self


class MetaTraderAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: str
    display_name: str
    platform: Literal["MT5", "MT4"]
    broker: str
    server: str
    login_reference: str
    credential_reference: str = Field(exclude=True, repr=False)
    terminal_path: str | None
    portable: bool
    account_mode: AccountMode = AccountMode.UNKNOWN
    enabled: bool = True
    execution_enabled: bool = False
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    broker_symbol: str
    allowed_strategy_ids: tuple[str, ...] = ()
    risk_profile_id: str | None = None
    created_at: datetime
    updated_at: datetime
    last_connected_at: datetime | None = None
    last_reconciled_at: datetime | None = None
