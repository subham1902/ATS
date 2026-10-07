"""Local operator account commands; no authority issuance or execution calls."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from ats.datasets.ingestion import data_root
from ats.market.metatrader.account_service import AccountService
from ats.market.metatrader.accounts import ConnectAccount
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


@router.post("/{account_id}/connect")
async def reconnect_account(account_id: str, request: Request) -> dict[str, Any]:
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
