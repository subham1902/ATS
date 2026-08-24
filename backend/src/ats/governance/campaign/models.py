"""Immutable R09 runtime configuration."""

from __future__ import annotations

from ats.contracts.common import ATSBaseModel
from pydantic import PositiveInt


class CampaignRuntimeConfiguration(ATSBaseModel):
    bar_duration_ms: PositiveInt


__all__ = ["CampaignRuntimeConfiguration"]
