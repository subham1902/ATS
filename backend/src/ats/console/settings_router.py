"""Dynamic settings control plane."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/settings", tags=["settings"])

class SettingField(BaseModel):
    name: str
    type: str
    required: bool
    allowed_values: list[Any] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    secret: bool = False
    restart_required: bool = False
    governance_locked: bool = False
    description: str

class SettingsSection(BaseModel):
    name: str
    fields: list[SettingField]

class SettingsSchema(BaseModel):
    version: str
    sections: list[SettingsSection]

class SettingsValue(BaseModel):
    effective_value: Any
    source_layer: str
    default_value: Any
    current_override: Any | None
    governance_state: str

class SettingsPayload(BaseModel):
    values: dict[str, dict[str, SettingsValue]]

_SCHEMA = SettingsSchema(
    version="1.0.0",
    sections=[
        SettingsSection(
            name="GENERAL",
            fields=[
                SettingField(
                    name="execution_mode",
                    type="string",
                    required=True,
                    allowed_values=[
                        "REPLAY_PAPER",
                        "SYNTHETIC_PAPER",
                        "LIVE_MARKET_PAPER",
                        "SHADOW",
                        "BACKTEST",
                    ],
                    description="The canonical execution mode for paper trading."
                ),
                SettingField(
                    name="live_money",
                    type="boolean",
                    required=True,
                    governance_locked=True,
                    description="CRITICAL: Enables real broker execution. Locked to false."
                )
            ]
        ),
        SettingsSection(
            name="BROKERS",
            fields=[
                SettingField(
                    name="primary_market_data_broker",
                    type="string",
                    required=True,
                    allowed_values=["upstox"],
                    description="The primary broker used for market data."
                ),
                SettingField(
                    name="account_read_broker",
                    type="string",
                    required=False,
                    allowed_values=["upstox"],
                    description="Broker used for account reading."
                )
            ]
        ),
        SettingsSection(
            name="PAPER TRADING",
            fields=[
                SettingField(
                    name="paper_starting_capital",
                    type="number",
                    required=True,
                    min_value=1000,
                    description="Starting capital for paper sessions.",
                ),
                SettingField(
                    name="max_concurrent_positions",
                    type="number",
                    required=True,
                    min_value=1,
                    max_value=20,
                    description="Max concurrent paper positions.",
                ),
                SettingField(
                    name="slippage_ticks",
                    type="number",
                    required=True,
                    min_value=0,
                    description="Slippage model ticks penalty.",
                ),
            ]
        ),
        SettingsSection(
            name="LIVE VISUALIZATION",
            fields=[
                SettingField(
                    name="chart_update_ms",
                    type="number",
                    required=True,
                    min_value=1,
                    max_value=5000,
                    description="Render loop frequency in milliseconds.",
                ),
                SettingField(
                    name="show_probability_heatmap",
                    type="boolean",
                    required=True,
                    description="Enable live probability overlays on the chart.",
                ),
                SettingField(
                    name="show_dynamic_sl_tp",
                    type="boolean",
                    required=True,
                    description=(
                        "Display real-time generated Stop Loss and Take Profit lines."
                    ),
                )
            ]
        ),
        SettingsSection(
            name="STRATEGY MODELS",
            fields=[
                SettingField(
                    name="active_strategy_engine",
                    type="string",
                    required=True,
                    allowed_values=[
                        "A04_DETERMINISTIC",
                        "A04_PROBABILISTIC",
                        "HYBRID_ENSEMBLE",
                    ],
                    description="Core engine used for signal generation.",
                ),
                SettingField(
                    name="probability_threshold",
                    type="number",
                    required=True,
                    min_value=0.1,
                    max_value=0.99,
                    description=(
                        "Minimum confidence required to render a prediction signal."
                    ),
                ),
                SettingField(
                    name="dynamic_sl_atr_multiplier",
                    type="number",
                    required=True,
                    min_value=0.5,
                    max_value=5.0,
                    description="ATR multiplier for trailing SL generation.",
                )
            ]
        )
    ]
)

_VALUES = {
    "GENERAL": {
        "execution_mode": SettingsValue(
            effective_value="LIVE_MARKET_PAPER",
            source_layer="SYSTEM_DEFAULT",
            default_value="REPLAY_PAPER",
            current_override="LIVE_MARKET_PAPER",
            governance_state="PAPER_ELIGIBLE",
        ),
        "live_money": SettingsValue(
            effective_value=False,
            source_layer="SYSTEM_DEFAULT",
            default_value=False,
            current_override=None,
            governance_state="GOVERNANCE_LOCKED",
        )
    },
    "BROKERS": {
        "primary_market_data_broker": SettingsValue(
            effective_value="upstox",
            source_layer="SYSTEM_DEFAULT",
            default_value="upstox",
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        ),
        "account_read_broker": SettingsValue(
            effective_value="upstox",
            source_layer="SYSTEM_DEFAULT",
            default_value=None,
            current_override="upstox",
            governance_state="PAPER_ELIGIBLE",
        )
    },
    "PAPER TRADING": {
        "paper_starting_capital": SettingsValue(
            effective_value=100000,
            source_layer="SYSTEM_DEFAULT",
            default_value=100000,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        ),
        "max_concurrent_positions": SettingsValue(
            effective_value=2,
            source_layer="SYSTEM_DEFAULT",
            default_value=2,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        ),
        "slippage_ticks": SettingsValue(
            effective_value=4,
            source_layer="SYSTEM_DEFAULT",
            default_value=4,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        )
    },
    "LIVE VISUALIZATION": {
        "chart_update_ms": SettingsValue(
            effective_value=16,
            source_layer="SYSTEM_DEFAULT",
            default_value=16,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        ),
        "show_probability_heatmap": SettingsValue(
            effective_value=True,
            source_layer="SYSTEM_DEFAULT",
            default_value=True,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        ),
        "show_dynamic_sl_tp": SettingsValue(
            effective_value=True,
            source_layer="SYSTEM_DEFAULT",
            default_value=True,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        )
    },
    "STRATEGY MODELS": {
        "active_strategy_engine": SettingsValue(
            effective_value="A04_PROBABILISTIC",
            source_layer="SYSTEM_DEFAULT",
            default_value="A04_DETERMINISTIC",
            current_override="A04_PROBABILISTIC",
            governance_state="PAPER_ELIGIBLE",
        ),
        "probability_threshold": SettingsValue(
            effective_value=0.65,
            source_layer="SYSTEM_DEFAULT",
            default_value=0.65,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        ),
        "dynamic_sl_atr_multiplier": SettingsValue(
            effective_value=2.0,
            source_layer="SYSTEM_DEFAULT",
            default_value=2.0,
            current_override=None,
            governance_state="PAPER_ELIGIBLE",
        )
    }
}

@router.get("/schema", response_model=SettingsSchema)
def get_schema() -> SettingsSchema:
    return _SCHEMA

@router.get("/values", response_model=SettingsPayload)
def get_values() -> SettingsPayload:
    return SettingsPayload(values=_VALUES)

@router.post("/values")
def update_values(payload: dict[str, Any]) -> dict[str, str]:
    # Reject governance locked updates
    if "GENERAL" in payload and "live_money" in payload["GENERAL"]:
        if payload["GENERAL"]["live_money"] is True:
            return {"status": "error", "message": "LIVE_MONEY is governance locked to false."}
    return {"status": "success"}

__all__ = ["router"]
