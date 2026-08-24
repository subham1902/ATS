from __future__ import annotations

from ats.market import (
    ApprovedFixture,
    DeterministicReplay,
    ReplayConfiguration,
    approved_manifest,
    create_approved_replay,
    nse_cash_alpha_v1_calendar,
)


def make_replay() -> DeterministicReplay:
    calendar = nse_cash_alpha_v1_calendar()
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    return create_approved_replay(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1,
        calendar,
        ReplayConfiguration(
            start_at=manifest.first_bar,
            received_delay_ms=250,
        ),
    )


__all__ = ["make_replay"]
