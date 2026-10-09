"""Operator-managed connections; execution consent does not mint authority."""

from __future__ import annotations

import json
import os
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
    AdoptAccount,
    ConnectAccount,
    ConnectionState,
    MetaTraderAccount,
)
from ats.market.metatrader.clock import load_clock_evidence
from ats.market.metatrader.connector import MetaTraderConnector
from ats.market.metatrader.control_config import AccountControlConfig
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

    def adopt_authenticated(self, request: AdoptAccount) -> dict[str, Any]:
        """Reuse terminal credential cache; adoption always starts monitor-only."""
        with self._lock:
            probe = Mt5AccountSession(
                {
                    "path": request.terminal_path,
                    "symbol": request.broker_symbol,
                    "timeout": 5000,
                    "_adopt": True,
                }
            )
            try:
                probe.initialize()
                login, server = probe.authenticated_reference()
            finally:
                probe.shutdown()
            reference = self.vault.store(login, "")
            now = datetime.now(UTC)
            account_id = "ACC-" + uuid4().hex
            account = MetaTraderAccount(
                account_id=account_id,
                display_name=request.display_name,
                platform="MT5",
                broker="",
                server=server,
                login_reference="vault:" + account_id,
                credential_reference=reference,
                terminal_path=request.terminal_path,
                portable=False,
                broker_symbol=request.broker_symbol,
                created_at=now,
                updated_at=now,
            )
            try:
                self.registry.save(account, "AUTHENTICATED_SESSION_ADOPTED_MONITOR_ONLY")
            except Exception:
                self.vault.delete(reference)
                raise
            return self.connect(account_id)

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
                    XauUsdDomain(broker_symbol=account.broker_symbol),
                    session,
                    clock_evidence=load_clock_evidence(self.clock_evidence_path(account_id))
                    if self.clock_evidence_path(account_id).exists()
                    else load_clock_evidence(Path(os.environ["ATS_MT5_CLOCK_EVIDENCE_FILE"]))
                    if os.environ.get("ATS_MT5_CLOCK_EVIDENCE_FILE")
                    else None,
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

    def clock_evidence_path(self, account_id: str) -> Path:
        self.registry.get(account_id)
        return self.root / "system" / "accounts" / "clock" / f"{account_id}.json"

    def refresh_clock(self, account_id: str) -> dict[str, Any]:
        with self._lock:
            connected = self._connections.get(account_id)
            if connected is None:
                raise ValueError("CONNECTED_ACCOUNT_REQUIRED")
            evidence = load_clock_evidence(self.clock_evidence_path(account_id))
            account = self.registry.get(account_id)
            evidence.normalize(evidence.tick_epoch_ms, account.server, datetime.now(UTC))
            with connected.lock:
                connected.connector.clock_evidence = evidence
                self.poll(account_id)
            return {
                "evidence_hash": evidence.evidence_hash,
                "captured_at": evidence.captured_at.isoformat(),
                "valid_seconds": evidence.valid_seconds,
                "offset_seconds": evidence.offset_seconds,
                "market": connected.connector.health(),
                "scope": "LIVE_ONLY_NOT_HISTORICAL_TIMEZONE",
            }

    def configure(
        self, account_id: str, config: AccountControlConfig, expected_revision: int
    ) -> None:
        with self._lock:
            self.registry.configure(account_id, config, expected_revision)

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

    def native_observer(self, account_id: str) -> dict[str, Any]:
        with self._lock:
            account = self.registry.get(account_id)
            connection = self._connections.get(account_id)
            if connection is None:
                return {"state": "UNKNOWN", "reason": "AUTHENTICATED_ACCOUNT_REQUIRED"}
            with connection.lock:
                profile = connection.snapshot.get("terminal_profile")
                if not isinstance(profile, str):
                    return {"state": "UNKNOWN", "reason": "TERMINAL_PROFILE_UNKNOWN"}
                target = (
                    Path(profile)
                    / "MQL5"
                    / "Files"
                    / "ATS"
                    / "SmallAccount"
                    / account_id
                    / "account-state.json"
                )
                try:
                    if target.stat().st_size > 1_000_000:
                        raise ValueError("NATIVE_STATE_TOO_LARGE")
                    payload = json.loads(target.read_text(encoding="utf-8"))
                    if (
                        payload.get("account_id") != account_id
                        or payload.get("canonical_symbol") != "XAUUSD"
                        or payload.get("source_server") != account.server
                        or payload.get("identity_matches") is not True
                    ):
                        raise ValueError("NATIVE_IDENTITY_MISMATCH")
                    age = datetime.now(UTC).timestamp() - target.stat().st_mtime
                    fields = (
                        "version",
                        "account_id",
                        "broker_symbol",
                        "observed_at_utc",
                        "utc_source",
                        "research_preset_hash",
                        "strategy_version",
                        "planned_risk_fraction",
                        "requested_daily_booked_loss_fraction",
                        "requested_monthly_booked_loss_fraction",
                        "signal_status",
                        "execution_authority",
                        "commands_supported",
                        "loss_baseline_status",
                        "terminal_algo_allowed",
                        "ea_trade_allowed",
                    )
                    return {
                        "state": "OBSERVING" if 0 <= age <= 10 else "STALE",
                        "file_age_seconds": age,
                        "provenance": "LOCAL_NATIVE_OBSERVER_FILE_NOT_AUTHORITY",
                        "observations": {key: payload.get(key) for key in fields},
                    }
                except (OSError, ValueError, TypeError, AttributeError):
                    return {"state": "UNKNOWN", "reason": "NATIVE_STATE_UNAVAILABLE_OR_INVALID"}

    def sizing_preview(
        self, account_id: str, side: str, entry: float, stop: float, costs: float
    ) -> dict[str, Any]:
        from decimal import Decimal

        with self._lock:
            config = self.registry.control_config(account_id)
            connected = self._connections.get(account_id)
            if config is None or connected is None:
                raise ValueError("CONNECTED_CONFIGURED_ACCOUNT_REQUIRED")
            with connected.lock:
                if connected.connector.health()["state"] != "LIVE":
                    raise ValueError("ACCEPTED_LIVE_QUOTE_REQUIRED")
                snapshot = connected.session.snapshot(connected.connector.domain.broker_symbol)
                equity = Decimal(str(snapshot.get("equity")))
                if not equity.is_finite() or equity <= 0:
                    raise ValueError("OBSERVED_EQUITY_REQUIRED")
                calculate = getattr(connected.session, "sizing_quote", None)
                if calculate is None:
                    raise ValueError("BROKER_SIZING_NOT_SUPPORTED")
                result: dict[str, Any] = calculate(
                    side,
                    entry,
                    stop,
                    float(equity * config.risk_per_trade),
                    costs,
                    float(config.max_volume),
                )
                result.update(
                    {
                        "configuration_revision": config.revision,
                        "account_id": account_id,
                        "period_budget_status": "UNVERIFIED_NOT_INCLUDED",
                        "grants_authority": False,
                    }
                )
                if result.get("state") == "PROVISIONAL" and Decimal(result["margin_cash"]) > min(
                    Decimal(result["free_margin"]), equity * config.margin_fraction
                ):
                    result["state"], result["reason"] = "REJECTED", "MARGIN_ALLOCATION_EXCEEDED"
                return result

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
                if self.registry.list():
                    raise ValueError("REGISTERED_ACCOUNT_CONNECTION_REQUIRED")
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
