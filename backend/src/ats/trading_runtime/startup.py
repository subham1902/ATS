"""Paper-only XAUUSD configuration preflight; offline research is supported."""

from __future__ import annotations

import json
import os

from ats.datasets.ingestion import data_root
from ats.market.domain import XauUsdDomain


def preflight() -> dict[str, object]:
    if os.environ.get("LIVE_MONEY", "FALSE").upper() != "FALSE":
        raise ValueError("PAPER_ONLY_VIOLATION")
    if os.environ.get("ATS_EXECUTION_DESTINATION", "PaperBroker") != "PaperBroker":
        raise ValueError("PAPER_ONLY_VIOLATION")
    domain = XauUsdDomain.from_environment()
    return {
        "canonical_symbol": domain.canonical_symbol,
        "provider": domain.provider,
        "broker_symbol": domain.broker_symbol,
        "mode": "OFFLINE_RESEARCH",
        "live_money": False,
        "execution_destination": "PaperBroker",
        "data_directory": str(data_root()),
        "authority": "A04_REQUIRED",
        "terminal_connection": "NOT_CHECKED",
    }


if __name__ == "__main__":
    print(json.dumps(preflight()))
