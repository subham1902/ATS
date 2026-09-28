# Copyright 2026 ATS Team
# SPDX-License-Identifier: Apache-2.0

"""Comprehensive End-to-End Verification Test for ATS <-> Laya Command Center Integration."""

import asyncio
import json
import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ats.ai.capital_advisor import CapitalAdvisorEngine
from ats.ai.laya_bridge import ATS_SPACE_ID, get_laya_bridge
from ats.ai.live_coach import CoachAlert
from ats.contracts.domain.types import Side
from ats.contracts.governance.models import OpportunityCandidate, RegisteredCode
from ats.contracts.governance.types import CandidateStatus


async def run_test():
    print("=" * 70)
    print("[*] STARTING ATS <-> LAYA INTEGRATION VERIFICATION")
    print("=" * 70)

    bridge = get_laya_bridge()
    print(f"1. Bridge initialized pointing to Laya DB: {bridge.db_path}")

    # 1. Ensure ATS Trading Space exists
    await bridge.ensure_ats_space()
    with sqlite3.connect(bridge.db_path) as db:
        cur = db.execute("SELECT space_id, name, color, icon FROM spaces WHERE space_id = ?", (ATS_SPACE_ID,))
        space_row = cur.fetchone()
        assert space_row is not None, "ATS Space was not created in Laya DB!"
        print(f"[OK] Laya Space Verified: ID={space_row[0]} | Name='{space_row[1]}' | Icon={space_row[3]} | Color={space_row[2]}")

    # 2. Publish an Opportunity Candidate
    now = datetime.now(UTC)
    cand_id = uuid4()
    candidate = OpportunityCandidate(
        schema_version="1.0",
        candidate_id=cand_id,
        candidate_version=1,
        instrument_id="MCX_GOLDM",
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        side=Side.BUY,
        event_definition_id=uuid4(),
        horizon_bars=15,
        target_outcome_code=RegisteredCode("OUTCOME_LONG_BREAKOUT"),
        calibrated_probability=Decimal("0.642"),
        expected_net_edge_r=0.28,
        expected_reward_risk=Decimal("2.65"),
        entry_conditions=(),
        proposed_stop_price=Decimal("75120.00"),
        proposed_target_price=Decimal("75850.00"),
        evidence_refs=(),
        status=CandidateStatus.ELIGIBLE,
        risk_decision_id=None,
        advisory_id=None,
        autonomy_token_id=None,
        created_at=now,
        expires_at=now.replace(year=now.year + 1),
        payload_hash="a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
    )

    card_id = await bridge.publish_opportunity_candidate(
        candidate,
        macro_context={
            "xauusd": "2684.50",
            "usdinr": "83.94",
            "basis_spread": "+40.00",
        },
    )
    print(f"[OK] Opportunity Candidate Published to Laya! Card ID: {card_id}")

    # Verify card in SQLite
    with sqlite3.connect(bridge.db_path) as db:
        cur = db.execute(
            "SELECT card_id, space_id, priority, persona, category, header, summary, suggested_actions FROM action_cards WHERE card_id = ?",
            (card_id,),
        )
        row = cur.fetchone()
        assert row is not None, "Action Card not found in Laya SQLite!"
        actions = json.loads(row[7])
        print(f"   - Header: {row[5]}")
        print(f"   - Priority: {row[2]} | Persona: {row[3]} | Category: {row[4]}")
        print(f"   - Suggested Actions count: {len(actions)}")
        for act in actions:
            print(f"     * [{act['action_type']}] {act['label']} (Target: {act['target_platform']})")

    # 3. Publish a Capital Feasibility Candidate
    advisor = CapitalAdvisorEngine()
    eval_res = advisor.evaluate(capital=Decimal("100000.00"), risk_profile="Balanced")
    if eval_res.eligible_candidates:
        cap_cand = eval_res.eligible_candidates[0]
        cap_card_id = await bridge.publish_capital_candidate(cap_cand, capital_amount=Decimal("100000.00"))
        print(f"[OK] Capital Advisor Candidate Published to Laya! Card ID: {cap_card_id}")

    # 4. Publish Live Coach Alert
    alert = CoachAlert(
        alert_id="alt-demo-001",
        event_type="SETUP_FOUND",
        severity="WARNING",
        message="High-Probability COMEX Impulse detected. MCX Gold Mini basis expanding to +40 pts.",
        instrument="MCX_FO|569003",
        current_price=Decimal("75420.00"),
        timestamp=now.isoformat(),
        grounding_data={"spread": "4.00", "state": "OPEN"},
    )
    coach_card_id = await bridge.publish_coach_alert(alert)
    print(f"[OK] Live Coach Alert Published to Laya! Card ID: {coach_card_id}")

    # 5. Publish Agent Trade Event
    agent_card_id = await bridge.publish_agent_trade(
        agent_name="Delta",
        trade_info={
            "side": "BUY",
            "instrument": "MCX_GOLDM",
            "price": "75,420.00",
            "lots": 1,
            "strategy": "Price x OI x Volume State Machine",
            "strategy_id": "S17_OI_VOLUME_MACHINE",
            "principal": 100000.0,
            "realized_pnl": 3450.0,
        },
    )
    print(f"[OK] Autonomous Agent Execution Published to Laya! Card ID: {agent_card_id}")

    # 6. Verify total cards in Laya ATS space
    with sqlite3.connect(bridge.db_path) as db:
        cur = db.execute("SELECT COUNT(*) FROM action_cards WHERE space_id = ?", (ATS_SPACE_ID,))
        total = cur.fetchone()[0]
        print(f"[*] Total Action Cards in Laya '{ATS_SPACE_ID}' Space: {total}")

    print("=" * 70)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_test())
