"""Local operator account commands; no authority issuance or execution calls."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ats.datasets.ingestion import data_root
from ats.market.metatrader.account_service import AccountService
from ats.market.metatrader.accounts import AdoptAccount, ConnectAccount
from ats.market.metatrader.control_config import AccountControlConfig
from ats.market.metatrader.credentials import WindowsCredentialVault
from ats.market.metatrader.registry import AccountRegistry

router = APIRouter(prefix="/v1/accounts", tags=["MetaTrader Accounts"])


class ExecutionConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


def service_of(request: Request) -> AccountService:
    with request.app.state.account_admin_lock:
        if request.app.state.account_service is None:
            root = data_root()
            request.app.state.account_service = AccountService(
                AccountRegistry(root / "system" / "accounts"),
                WindowsCredentialVault(root / "system" / "credentials"),
                root,
            )
        return cast(AccountService, request.app.state.account_service)


async def _call(operation: Any, *arguments: Any, **options: Any) -> Any:
    try:
        return await asyncio.to_thread(operation, *arguments, **options)
    except KeyError:
        raise HTTPException(404, "ACCOUNT_NOT_FOUND") from None
    except ValueError:
        raise HTTPException(409, "ACCOUNT_CONFIGURATION_OR_STATE_CONFLICT") from None
    except Exception:
        raise HTTPException(503, "ACCOUNT_SERVICE_UNAVAILABLE") from None


@router.get("")
async def list_accounts(request: Request) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = await _call(service_of(request).list)
    return result


@router.post("", status_code=201)
async def connect_account(body: ConnectAccount, request: Request) -> dict[str, Any]:
    worker = getattr(request.app.state, "standalone_market_worker", None)
    if worker is not None:
        await worker.stop()
    result: dict[str, Any] = await _call(service_of(request).connect_new, body)
    return result


@router.post("/adopt", status_code=201)
async def adopt_account(body: AdoptAccount, request: Request) -> dict[str, Any]:
    worker = getattr(request.app.state, "standalone_market_worker", None)
    if worker is not None:
        await worker.stop()
    result: dict[str, Any] = await _call(service_of(request).adopt_authenticated, body)
    return result


@router.post("/{account_id}/connect")
async def reconnect_account(account_id: str, request: Request) -> dict[str, Any]:
    worker = getattr(request.app.state, "standalone_market_worker", None)
    if worker is not None:
        await worker.stop()
    result: dict[str, Any] = await _call(service_of(request).connect, account_id)
    return result


@router.post("/{account_id}/disconnect")
async def disconnect_account(account_id: str, request: Request) -> dict[str, Any]:
    result: dict[str, Any] = await _call(service_of(request).disconnect, account_id)
    return result


@router.post("/{account_id}/execution")
async def execution_consent(
    account_id: str, body: ExecutionConsent, request: Request
) -> dict[str, Any]:
    result: dict[str, Any] = await _call(
        service_of(request).set_execution, account_id, body.enabled
    )
    return result


class ConfigureAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int
    config: AccountControlConfig


@router.get("/{account_id}/configuration")
async def get_configuration(account_id: str, request: Request) -> dict[str, Any]:
    config = await _call(service_of(request).registry.control_config, account_id)
    return {
        "configuration": config.model_dump(mode="json") if config else None,
        "grants_authority": False,
    }


@router.put("/{account_id}/configuration")
async def configure_account(
    account_id: str, body: ConfigureAccount, request: Request
) -> dict[str, Any]:
    from ats.console.strategy_os_router import store_of

    try:
        for assignment in body.config.assignments:
            record = store_of().get(assignment.strategy_id, assignment.strategy_version)
            if record.status == "RETIRED":
                raise ValueError("RETIRED_STRATEGY")
    except (KeyError, ValueError):
        raise HTTPException(409, "STRATEGY_VERSION_INVALID") from None
    service = service_of(request)
    await _call(service.configure, account_id, body.config, body.expected_revision)
    return await get_configuration(account_id, request)


@router.get("/{account_id}/readiness")
async def account_readiness(account_id: str, request: Request) -> dict[str, Any]:
    from ats.console.strategy_os_router import store_of

    service = service_of(request)
    view = await _call(service.view, account_id)
    config = await _call(service.registry.control_config, account_id)
    reasons = [
        "EXTERNAL_ROUTING_NOT_COMMISSIONED",
        "PERIOD_LEDGER_NOT_COMMISSIONED",
        "RECONCILIATION_NOT_COMMISSIONED",
    ]
    if view["account"]["connection_state"] != "CONNECTED":
        reasons.append("ACCOUNT_DISCONNECTED")
    if not view["account"]["execution_enabled"]:
        reasons.append("OPERATOR_CONSENT_REQUIRED")
    if view["market"]["state"] != "LIVE":
        reasons.append("FRESH_ACCEPTED_MARKET_DATA_REQUIRED")
    if config is None:
        reasons.append("RISK_CONFIGURATION_REQUIRED")
    else:
        if config.paused:
            reasons.append("ACCOUNT_ENTRIES_PAUSED")
        assignments = [a for a in config.assignments if a.enabled]
        if not assignments:
            reasons.append("STRATEGY_ASSIGNMENT_REQUIRED")
        for assignment in assignments:
            try:
                record = store_of().get(assignment.strategy_id, assignment.strategy_version)
                if record.status not in {"DEMO", "MICRO_LIVE", "ACTIVE"}:
                    reasons.append(f"STRATEGY_NOT_ELIGIBLE:{assignment.strategy_id}")
            except KeyError:
                reasons.append(f"STRATEGY_VERSION_UNKNOWN:{assignment.strategy_id}")
    return {
        "account_id": account_id,
        "effective_execution_enabled": False,
        "reason_codes": reasons,
        "configuration_revision": config.revision if config else None,
    }


class SizingPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    side: Literal["BUY", "SELL"]
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    roundtrip_cost_per_lot: float = Field(ge=0)


@router.post("/{account_id}/sizing-preview")
async def sizing_preview(account_id: str, body: SizingPreview, request: Request) -> dict[str, Any]:
    result: dict[str, Any] = await _call(
        service_of(request).sizing_preview,
        account_id,
        body.side,
        body.entry,
        body.stop,
        body.roundtrip_cost_per_lot,
    )
    return result


@router.get("/{account_id}/native-observer")
async def native_observer(account_id: str, request: Request) -> dict[str, Any]:
    result: dict[str, Any] = await _call(service_of(request).native_observer, account_id)
    return result


@router.post("/{account_id}/clock/refresh")
async def refresh_clock(account_id: str, request: Request) -> dict[str, Any]:
    result: dict[str, Any] = await _call(service_of(request).refresh_clock, account_id)
    return result
