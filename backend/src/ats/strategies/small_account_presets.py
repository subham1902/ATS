"""Versioned research settings. Presets cannot grant execution eligibility."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SmallAccountPreset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    version: Literal["GOLD-TRIPLE-SMALL-ACCOUNT-V3"] = "GOLD-TRIPLE-SMALL-ACCOUNT-V3"
    preset_id: str = Field(min_length=1)
    strategy_id: Literal["XAU-019", "XAU-020"]
    strategy_version: int = Field(ge=1)
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    account_currency: Literal["USD"] = "USD"
    research_initial_capital: Decimal = Field(gt=0)
    status: Literal["HISTORICAL_FORWARD_CANDIDATE"] = "HISTORICAL_FORWARD_CANDIDATE"
    execution_eligible: Literal[False] = False
    direction: Literal["LONG", "BOTH"]
    tactical_seconds: Literal[300] = 300
    structural_lookback: Literal[1, 3]
    risk_fraction: Decimal = Field(gt=0, le=Decimal("0.02"))
    target_r: Decimal = Field(ge=1, le=5)
    profit_protection: bool
    maximum_hold_minutes: int = Field(gt=0, le=240)
    entry_start_hour_utc: Literal[12] = 12
    entry_end_hour_utc: Literal[17] = 17
    weekdays_utc: tuple[int, ...]
    daily_net_booked_loss_cap: Literal["0.03"] = "0.03"
    monthly_net_booked_loss_cap: Literal["0.08"] = "0.08"
    equity_reference: Literal["START_OF_PERIOD"] = "START_OF_PERIOD"
    internal_daily_budget: Literal["0.025"] = "0.025"
    internal_monthly_budget: Literal["0.06"] = "0.06"
    maximum_concurrent_positions: Literal[1] = 1
    maximum_entries_per_day: Literal[3] = 3
    halt_after_losing_trades: Literal[2] = 2
    reentry_delay_seconds: Literal[900] = 900
    maximum_margin_fraction: Literal["0.30"] = "0.30"
    maximum_volume: Literal["0.10"] = "0.10"
    target_grid_policy: Literal["TOWARD_ENTRY"] = "TOWARD_ENTRY"
    parent_retest_level: Literal["M15_CLOSE", "H4_CLOSE"]
    volume_provenance: Literal["UNKNOWN_SOURCE_VOLUME", "NOT_REQUIRED"]
    dataset_bid_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    dataset_ask_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    selection_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    grid_verification_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def canonical_variant(self) -> SmallAccountPreset:
        if self.research_initial_capital != 1000:
            raise ValueError("PRESET_ONLY_RESEARCHED_AT_1000_USD")
        expected = (
            ("LONG", 1, Decimal("0.015"), 120, (1, 2, 3), "H4_CLOSE", "NOT_REQUIRED")
            if self.strategy_id == "XAU-020"
            else (
                "BOTH",
                3,
                Decimal("0.0125"),
                240,
                (0, 1, 2, 3, 4),
                "M15_CLOSE",
                "UNKNOWN_SOURCE_VOLUME",
            )
        )
        actual = (
            self.direction,
            self.structural_lookback,
            self.risk_fraction,
            self.maximum_hold_minutes,
            self.weekdays_utc,
            self.parent_retest_level,
            self.volume_provenance,
        )
        if actual != expected or self.target_r != 2 or self.profit_protection:
            raise ValueError("SELECTED_RESEARCH_SETTINGS_MISMATCH")
        return self

    @property
    def preset_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def native_inputs(self, account_id: str, broker_symbol: str) -> dict[str, str]:
        """Observer inputs; no credentials, order commands or authority."""
        if not account_id.startswith("ACC-") or not account_id[4:].isalnum():
            raise ValueError("INVALID_INTERNAL_ACCOUNT_ID")
        if not broker_symbol or any(c in broker_symbol for c in "\r\n="):
            raise ValueError("INVALID_BROKER_SYMBOL")
        # Python weekdays: Mon=0. Native mask: Sun=0.
        weekday_mask = sum(1 << ((d + 1) % 7) for d in self.weekdays_utc)
        return {
            "ATSAccountId": account_id,
            "BrokerSymbol": broker_symbol,
            "ResearchPresetHash": self.preset_hash,
            "Strategy1Id": "XAU-018",
            "Strategy2Id": "XAU-019",
            "Strategy3Id": "XAU-020",
            "StrategyVersion": str(self.strategy_version),
            "RequireDemoAccount": "true",
            "PublishSeconds": "2",
            "ResearchRiskFraction": str(self.risk_fraction),
            "RequestedDailyLossFraction": self.daily_net_booked_loss_cap,
            "RequestedMonthlyLossFraction": self.monthly_net_booked_loss_cap,
            "ClockProfileCsv": "",
            "ClockProfileHash": "",
            "HistoryWarmupDays": "120",
            "TacticalSeconds": str(self.tactical_seconds),
            "TacticalLookback": str(self.structural_lookback),
            "EnabledStrategyMask": "4" if self.strategy_id == "XAU-020" else "2",
            "TargetR": str(self.target_r),
            "EnableProfitProtection": "false",
            "MaximumHoldMinutes": str(self.maximum_hold_minutes),
            "EstimatedRoundTripCostPerLot": "44.0",
            "MinimumEntryHourUTC": "12",
            "MaximumEntryHourUTC": "17",
            "AllowedWeekdayMask": str(weekday_mask),
            "AllowedDirectionMask": "1" if self.direction == "LONG" else "3",
        }
