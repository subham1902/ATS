"""Operator-managed connections; execution consent does not mint authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from ats.market.domain import XauUsdDomain
from ats.market.fabric import MarketDataFabric
from ats.market.metatrader.account_session import AccountSession, Mt5AccountSession
from ats.market.metatrader.accounts import (
    AccountMode,
    ConnectAccount,
    ConnectionState,
    MetaTraderAccount,
)
from ats.market.metatrader.connector import MetaTraderConnector
from ats.market.metatrader.credentials import CredentialVault
from ats.market.metatrader.journal import ObservationJournal
from ats.market.metatrader.registry import AccountRegistry


@dataclass
class _ConnectedAccount:
    session: AccountSession
    connector: MetaTraderConnector
    fabric: MarketDataFabric
    journal: ObservationJournal
    snapshot: dict[str, Any] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)


def _session_factory(account: MetaTraderAccount, login: str, password: str) -> AccountSession:
    return Mt5AccountSession(
        {
            "path": account.terminal_path,
            "login": int(login),
            "password": password,
            "server": account.server,
            "portable": account.portable,
            "timeout": 5000,
            "symbol": account.broker_symbol,
        }
    )


class AccountService:
    def __init__(
        self,
        registry: AccountRegistry,
        vault: CredentialVault,
        root: Path,
        factory: Callable[[MetaTraderAccount, str, str], AccountSession] = _session_factory,
    ) -> None:
        self.registry, self.vault, self.root, self.factory = registry, vault, root, factory
        self._connections: dict[str, _ConnectedAccount] = {}
        self._lock = RLock()
        # Never resurrect a connection or execution consent after a restart.
        for account in registry.list():
            self._save(
                account,
                "PROCESS_RESTART",
                connection_state=ConnectionState.DISCONNECTED,
                execution_enabled=False,
            )

    def _save(self, account: MetaTraderAccount, action: str, **changes: Any) -> MetaTraderAccount:
        updated = account.model_copy(update={**changes, "updated_at": datetime.now(UTC)})
        self.registry.save(updated, action)
        return updated

    def connect_new(self, request: ConnectAccount) -> dict[str, Any]:
        with self._lock:
            reference = self.vault.store(
                request.login.get_secret_value(), request.password.get_secret_value()
            )
            now = datetime.now(UTC)
            account_id = "ACC-" + uuid4().hex
            account = MetaTraderAccount(
                account_id=account_id,
                display_name=request.display_name,
                platform=request.platform,
                broker=request.broker,
                server=request.server,
                login_reference="vault:" + account_id,
                credential_reference=reference,
                terminal_path=request.terminal_path,
                portable=request.portable,
                broker_symbol=request.broker_symbol,
                created_at=now,
                updated_at=now,
            )
            try:
                self.registry.save(account, "ACCOUNT_REGISTERED")
            except Exception:
                self.vault.delete(reference)
                raise
            return self.connect(account_id, enable=request.action == "CONNECT_AND_ENABLE_EXECUTION")

    def connect(self, account_id: str, *, enable: bool = False) -> dict[str, Any]:
        with self._lock:
            account = self.registry.get(account_id)
            self.disconnect(account_id)
            if account.platform == "MT4":
                self._save(
                    account,
                    "MT4_TRANSPORT_REQUIRED",
                    connection_state=ConnectionState.NOT_CONFIGURED,
                    execution_enabled=False,
                )
                return self.view(account_id)
            account = self._save(
                account,
                "CONNECT_REQUESTED",
                connection_state=ConnectionState.CONNECTING,
                execution_enabled=False,
            )
            session: AccountSession | None = None
            try:
                login, password = self.vault.load(account.credential_reference)
                session = self.factory(account, login, password)
                connector = MetaTraderConnector(
                    XauUsdDomain(broker_symbol=account.broker_symbol), session
                )
                if not connector.connect():
                    raise ValueError("CONNECTION_FAILED")
                snapshot = session.snapshot(account.broker_symbol)
                profile = snapshot.get("terminal_profile")
                if not isinstance(profile, str) or not profile:
                    raise ValueError("TERMINAL_PROFILE_UNKNOWN")
                for other in self._connections.values():
                    if (
                        str(other.snapshot.get("terminal_profile", "")).casefold()
                        == profile.casefold()
                    ):
                        raise ValueError("TERMINAL_PROFILE_SHARED")
                fabric = MarketDataFabric(
                    source_label="MT5",
                    authority_class="BROKER_TICK_PROXY",
                    stale_after_seconds=connector.domain.stale_after_seconds,
                )
                fabric.tick_size = connector.metadata.tick_size if connector.metadata else None
                self._connections[account_id] = _ConnectedAccount(
                    session,
                    connector,
                    fabric,
                    ObservationJournal(self.root / "xauusd" / "live" / account_id),
                    snapshot,
                )
                self._save(
                    account,
                    "ACCOUNT_CONNECTED",
                    connection_state=ConnectionState.CONNECTED,
                    account_mode=AccountMode(snapshot["account_mode"]),
                    execution_enabled=enable,
                    last_connected_at=datetime.now(UTC),
                )
                self.poll(account_id)
            except Exception:
                if session is not None:
                    try:
                        session.shutdown()
                    except Exception:
                        pass
                self._connections.pop(account_id, None)
                self._save(
                    account,
                    "CONNECTION_FAILED",
                    connection_state=ConnectionState.ERROR,
                    execution_enabled=False,
                )
            return self.view(account_id)

    def disconnect(self, account_id: str) -> dict[str, Any]:
        with self._lock:
            account = self.registry.get(account_id)
            connected = self._connections.pop(account_id, None)
            if connected:
                with connected.lock:
                    try:
                        connected.session.shutdown()
                    except Exception:
                        pass
            self._save(
                account,
                "ACCOUNT_DISCONNECTED",
                connection_state=ConnectionState.DISCONNECTED,
                execution_enabled=False,
            )
            return self.view(account_id)

    def set_execution(self, account_id: str, enabled: bool) -> dict[str, Any]:
        with self._lock:
            account = self.registry.get(account_id)
            if enabled and account.connection_state != ConnectionState.CONNECTED:
                raise ValueError("CONNECTED_ACCOUNT_REQUIRED")
            self._save(
                account,
                "EXECUTION_CONSENT_ENABLED" if enabled else "EXECUTION_DISABLED",
                execution_enabled=enabled,
            )
            return self.view(account_id)

    def poll(self, account_id: str) -> None:
        connected = self._connections.get(account_id)
        if connected is None:
            return
        with connected.lock:
            if self._connections.get(account_id) is not connected:
                return
            try:
                snapshot = connected.session.snapshot(connected.connector.domain.broker_symbol)
                if snapshot.get("terminal_profile") != connected.snapshot.get("terminal_profile"):
                    raise ValueError("TERMINAL_PROFILE_CHANGED")
                connected.snapshot = snapshot
                observation = connected.connector.latest_tick()
                if observation is not None:
                    # Admission occurs before journal/fan-out; duplicates are not written.
                    connected.fabric.publish(observation, before_commit=connected.journal.append)
            except Exception:
                # Account failure blocks its consent; other accounts remain independent.
                connected.snapshot = {}
                try:
                    connected.connector.shutdown()
                except Exception:
                    pass
                account = self.registry.get(account_id)
                self._save(
                    account,
                    "ACCOUNT_STATE_UNKNOWN",
                    connection_state=ConnectionState.ERROR,
                    execution_enabled=False,
                )

    def market_connection(
        self, account_id: str | None = None
    ) -> tuple[MetaTraderConnector, MarketDataFabric] | None:
        with self._lock:
            if account_id is not None:
                self.registry.get(account_id)
                connection = self._connections.get(account_id)
                if connection is None:
                    raise ValueError("ACCOUNT_MARKET_DISCONNECTED")
            elif len(self._connections) == 1:
                connection = next(iter(self._connections.values()))
            elif len(self._connections) > 1:
                raise ValueError("MARKET_ACCOUNT_SELECTION_REQUIRED")
            else:
                return None
            return connection.connector, connection.fabric

    def view(self, account_id: str) -> dict[str, Any]:
        account = self.registry.get(account_id)
        connected = self._connections.get(account_id)
        snapshot = dict(connected.snapshot) if connected else {}
        snapshot.pop("terminal_profile", None)
        quote = connected.fabric.latest("XAUUSD") if connected else None
        return {
            "account": account.model_dump(mode="json"),
            "observed": snapshot,
            "market": connected.connector.health() if connected else {"state": "DISCONNECTED"},
            "quote": quote.model_dump(mode="json") if quote else None,
            "execution_gate": "EXTERNAL_ROUTING_NOT_IMPLEMENTED",
            "risk_state": "RISK_PROFILE_REQUIRED" if account.risk_profile_id is None else "UNKNOWN",
            "reconciliation_state": "BROKER_SNAPSHOT_ONLY" if snapshot else "UNKNOWN",
        }

    def list(self) -> list[dict[str, Any]]:
        return [self.view(account.account_id) for account in self.registry.list()]

    def shutdown(self) -> None:
        for account_id in tuple(self._connections):
            self.disconnect(account_id)
