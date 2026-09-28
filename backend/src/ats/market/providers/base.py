"""Base interface for all broker connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BrokerCapabilities(BaseModel):
    market_quotes: bool = True
    streaming: bool = True
    historical_data: bool = True
    instruments: bool = True
    market_status: bool = True
    positions_read: bool = True
    orders_read: bool = True
    sandbox_support: bool = False
    paper_execution: bool = True
    live_execution: bool = False
    execution_state: str = "DISABLED"
    live_order_route: str = "NON_EXISTENT"

class BrokerManifest(BaseModel):
    broker_id: str
    display_name: str
    supported_data_modes: list[str]
    auth_modes: list[str]
    capabilities: BrokerCapabilities
    status: str
    live_execution_mode: str = "DISABLED"

class BrokerConnector(ABC):
    """Abstract interface for all broker connections.
    
    CRITICAL RULE: DO NOT implement `place_order` or any real execution methods
    in the active interface. This interface is strictly for Market Data and
    Account Read operations.
    """
    
    @property
    @abstractmethod
    def manifest(self) -> BrokerManifest:
        pass
        
    @abstractmethod
    def get_connection_state(self) -> str:
        """Return 'CONNECTED', 'AUTH_REQUIRED', etc."""
        pass
        
    @abstractmethod
    def authenticate(self, credentials: dict[str, str]) -> bool:
        pass
        
    @abstractmethod
    def get_quote(self, instrument_id: str) -> dict[str, Any] | None:
        pass
        
    @abstractmethod
    def get_positions_readonly(self) -> list[dict[str, Any]]:
        pass
