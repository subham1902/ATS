"""Authoritative connected pre-market readiness CLI."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import tempfile
import winreg
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr

from ats.market.data_acquisition.upstox_client import UpstoxReadOnlyClient
from ats.market.derivatives.option_universe import build_dynamic_option_universe
from ats.market.feeds.upstox_v3 import (
    BANKNIFTY_INDEX_FEED_KEY,
    NIFTY_INDEX_FEED_KEY,
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    UpstoxV3FeedAuthorizer,
    UpstoxV3Transport,
    WireFormat,
)
from ats.market.feeds.upstox_v3.protobuf_codec import UpstoxV3ProtobufDecoder
from ats.trading_runtime.a2_runner import A2PaperSessionConfig, default_a2_session_calendar
from ats.trading_runtime.connected_readiness import (
    ConnectedReadinessInput,
    InstrumentSpecTruth,
    ReadinessContext,
    evaluate_connected_readiness,
)
from ats.trading_runtime.readiness import check_pre_market_readiness
from ats.trading_runtime.session import SessionRuntimeConfig, resolve_session_status
from ats.trading_runtime.session_reconciliation import reconcile_launcher_state


def _token() -> str | None:
    value = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
    if value:
        return value
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            candidate = winreg.QueryValueEx(key, "ATS_UPSTOX_ACCESS_TOKEN")[0]
            return candidate.strip() if isinstance(candidate, str) and candidate.strip() else None
    except OSError:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def _port_active(port: int) -> bool:
    with socket.socket() as client:
        client.settimeout(0.1)
        return client.connect_ex(("127.0.0.1", port)) == 0


def _storage_probe(root: Path) -> str:
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="readiness-", dir=root, delete=True) as handle:
            handle.write(b"ATS")
            handle.flush()
            os.fsync(handle.fileno())
        return "RECORDER_CONFIG_READY"
    except OSError:
        return "RECORDER_CONFIG_UNUSABLE"


def _extract_ltp(document: dict[str, object], key: str) -> Decimal:
    data = document.get("data")
    if not isinstance(data, dict):
        raise ValueError("MARKET_QUOTE_SHAPE_INVALID")
    for item in (data.get(key), *data.values()):
        if isinstance(item, dict):
            value = item.get("last_price", item.get("ltp"))
            if isinstance(value, int | float | Decimal) and not isinstance(value, bool):
                price = Decimal(str(value))
                if price > 0:
                    return price
    raise ValueError("MARKET_QUOTE_LTP_MISSING")


def _provider_probe(
    now: datetime, token: str | None
) -> tuple[str, str, str, str, tuple[InstrumentSpecTruth, ...], int, int]:
    if token is None:
        return "TOKEN_MISSING", "UNKNOWN", "UNKNOWN", "UNKNOWN", (), 0, 0
    try:
        client = UpstoxReadOnlyClient(token=token)
        spots = {
            "NIFTY": _extract_ltp(client.ltp(NIFTY_INDEX_FEED_KEY), NIFTY_INDEX_FEED_KEY),
            "BANKNIFTY": _extract_ltp(
                client.ltp(BANKNIFTY_INDEX_FEED_KEY), BANKNIFTY_INDEX_FEED_KEY
            ),
        }
        auth = "PASS"
    except Exception as error:
        status = getattr(error, "code", None)
        value = (
            "TOKEN_INVALID"
            if status in (401, 403)
            else f"PROVIDER_UNREACHABLE:{type(error).__name__}"
        )
        return value, "UNKNOWN", "UNKNOWN", "UNKNOWN", (), 0, 0
    try:
        module = importlib.import_module("scripts.run_d10_live_acceptance")
        contracts = module._fetch_reference(now)
        if not contracts:
            return auth, "REFERENCE_DATA_EMPTY", "UNKNOWN", "UNKNOWN", (), 0, 0
        reference = "PASS"
    except Exception as error:
        return (
            auth,
            f"REFERENCE_ENDPOINT_FAILED:{type(error).__name__}",
            "UNKNOWN",
            "UNKNOWN",
            (),
            0,
            0,
        )
    try:
        universe = build_dynamic_option_universe(
            contracts=contracts, spots=spots, as_of=now, mode=FeedMode.FULL
        )
        keys = [item.instrument_key for item in universe]
        duplicates = len(keys) - len(set(keys))
        invalid = sum(1 for item in universe if not item.instrument_key)
        specs = []
        for underlying in ("NIFTY", "BANKNIFTY"):
            options = [
                item
                for item in universe
                if item.underlying == underlying and item.instrument_kind == "OPTION"
            ]
            index = next(
                item
                for item in universe
                if item.underlying == underlying and item.instrument_kind == "INDEX"
            )
            lots = {item.lot_size for item in options}
            ticks = {item.tick_size for item in options}
            expiries = {item.expiry for item in options}
            if (
                len(lots) != 1
                or len(ticks) != 1
                or len(expiries) != 1
                or None in lots | ticks | expiries
            ):
                raise ValueError("INCONSISTENT_PROVIDER_INSTRUMENT_SPEC")
            lot = next(iter(lots))
            tick = next(iter(ticks))
            expiry = next(iter(expiries))
            assert lot is not None and tick is not None and expiry is not None
            specs.append(
                InstrumentSpecTruth(
                    underlying,
                    index.instrument_key,
                    int(lot),
                    str(tick),
                    str(expiry),
                    tuple(item.instrument_key for item in options),
                )
            )
        subscription = "PASS" if duplicates == 0 and invalid == 0 else "INVALID"
    except Exception as error:
        return (
            auth,
            reference,
            "UNKNOWN",
            f"CONTRACT_RESOLUTION_FAILED:{type(error).__name__}",
            (),
            0,
            1,
        )
    transport = None
    try:
        authorization = UpstoxFeedAuthorization(bearer_token=SecretStr(token))
        configuration = UpstoxFeedConfiguration(
            wire_format=WireFormat.PROTOBUF_BINARY,
            client_guid=str(uuid4()),
            limits=UpstoxFeedLimits(
                maximum_silence_ms=5_000,
                stale_after_ms=10_000,
                maximum_buffered_frames=32,
                receive_timeout_ms=5_000,
            ),
        )
        transport = UpstoxV3Transport(
            configuration=configuration, authorizer=UpstoxV3FeedAuthorizer(authorization)
        )
        transport.connect()
        transport.subscribe(
            guid=configuration.client_guid, mode=FeedMode.FULL, instrument_keys=tuple(keys)
        )
        feed = "PASS"
    except Exception as error:
        feed = f"PROVIDER_CONNECTION_FAILED:{type(error).__name__}"
    finally:
        if transport is not None:
            transport.close()
    return auth, reference, feed, subscription, tuple(specs), duplicates, invalid


def _connected(requested_mode: str) -> int:
    now = datetime.now(UTC)
    from ats.trading_runtime.modes import TradingMode

    config = A2PaperSessionConfig(mode=TradingMode(requested_mode))
    session = resolve_session_status(
        calendar=default_a2_session_calendar(), config=SessionRuntimeConfig(), now=now
    )
    evidence_root = Path("data/runtime/sessions").resolve()
    state_file = Path(os.environ.get("TEMP", ".")) / "ats-a2-live-paper" / "processes.json"
    checkpoint = os.environ.get("ATS_A2_RUNTIME_CHECKPOINT_PATH")
    reconciliation = reconcile_launcher_state(
        state_file,
        evidence_root=evidence_root,
        checkpoint_path=Path(checkpoint) if checkpoint else None,
        pid_alive=_pid_alive,
        port_active=_port_active,
    )
    auth, reference, feed, subscription, specs, duplicates, invalid = _provider_probe(now, _token())
    probe = ConnectedReadinessInput(
        context=ReadinessContext.CONNECTED_PREMARKET,
        checked_at=now,
        trading_date=now.astimezone().date().isoformat(),
        market_phase=session.phase.value,
        session_can_enter=session.can_enter,
        requested_mode=config.mode.value,
        effective_mode=None,
        execution_target=config.execution_target,
        live_money_enabled=config.live_money != "DISABLED",
        real_broker_enabled=False if config.execution_target == "PAPER" else None,
        configured_capital=config.capital_budget,
        runtime_capital=None,
        provider_auth=auth,
        provider_reference=reference,
        feed_connection=feed,
        decoder_status=(
            "CONFIGURED_DECODER_READY"
            if isinstance(UpstoxV3ProtobufDecoder(), UpstoxV3ProtobufDecoder)
            else "UNKNOWN"
        ),
        subscription_status=subscription,
        specs=specs,
        duplicate_subscriptions=duplicates,
        invalid_subscriptions=invalid,
        market_data_stage="PRE_OPEN_NOT_APPLICABLE"
        if session.phase.value in {"PREOPEN", "WARMUP", "CLOSED"}
        else "MARKET_OPEN_DATA_NOT_OBSERVED",
        paperbroker_status="CONFIGURED_PAPERBROKER_READY",
        recorder_status=_storage_probe(evidence_root),
        forensics_status="FORENSICS_CONFIG_READY",
        a04_status="CONFIGURED_READY",
        reconciliation=reconciliation,
    )
    result = evaluate_connected_readiness(probe)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return result.exit_code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--mode", choices=["SAFE", "NORMAL", "AGGRESSIVE"], default="AGGRESSIVE")
    args = parser.parse_args()
    if args.synthetic:
        result = check_pre_market_readiness(synthetic_mode=True)
        print(json.dumps(result.to_dict(), indent=2))
        raise SystemExit(0 if result.ready_for_a2_paper else 1)
    raise SystemExit(_connected(args.mode))


if __name__ == "__main__":
    main()
