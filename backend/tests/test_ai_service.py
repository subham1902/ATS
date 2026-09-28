import asyncio
from decimal import Decimal

import pytest
from ats.ai.capital_advisor import CapitalAdvisorEngine
from ats.ai.live_coach import LiveCoachEngine
from ats.ai.service import AIQueryRequest, ATSAIService
from ats.ai.tools import ToolDefinition


def test_ai_service_read_only_tools():
    async def _test():
        service = ATSAIService()
        tools = service.tool_registry.get_definitions()
        assert len(tools) >= 5
        for t in tools:
            assert t.read_only is True

        # Test executing snapshot
        res = await service.tool_registry.execute(
            "market.get_snapshot", {"instrument": "MCX_FO|569003"}
        )
        assert res.status == "SUCCESS"
        assert res.data["instrument"] == "MCX_FO|569003"

    asyncio.run(_test())


def test_ai_mutation_tool_rejected():
    service = ATSAIService()
    with pytest.raises(ValueError, match="Mutation tools strictly forbidden"):
        service.tool_registry.register(
            ToolDefinition(
                name="order.place",
                category="order",
                description="Illegal order placement",
                parameters=[],
                read_only=False,
            ),
            lambda: None,
        )


def test_capital_advisor_deterministic_evaluation():
    engine = CapitalAdvisorEngine()
    # Test ₹30,000 query test
    res = engine.evaluate(capital=Decimal("30000.00"), risk_profile="Balanced")
    assert res.available_capital == Decimal("30000.00")
    assert res.max_risk_amount == Decimal("450.00")  # 1.5% of 30,000
    assert len(res.eligible_candidates) >= 1
    # Check that probabilities are not None and have provenance
    for c in res.eligible_candidates:
        assert 0.0 < c.calibrated_win_prob < 1.0
        assert len(c.probability_provenance) > 0


def test_live_coach_deterministic_alerts():
    coach = LiveCoachEngine()
    # Trigger abnormal spread
    alerts = coach.evaluate_tick(
        instrument="MCX_FO|569003",
        price=Decimal("75420.00"),
        spread=Decimal("20.00"),
    )
    assert any(a.event_type == "SPREAD_ABNORMAL" for a in alerts)

    # Trigger TP1 reached on active long position (entry 75250, TP 75850)
    tp_alerts = coach.evaluate_tick(
        instrument="MCX_FO|569003",
        price=Decimal("75860.00"),
        spread=Decimal("4.00"),
    )
    assert any(a.event_type == "TP1_REACHED" for a in alerts + tp_alerts)


def test_ai_service_query_modes():
    async def _test():
        service = ATSAIService()

        # Capital Advisor mode
        cap_res = await service.process_query(
            AIQueryRequest(
                query="I have ₹30,000. Show opportunities.",
                mode="Capital Advisor",
                capital_input=Decimal("30000.00"),
            )
        )
        assert "Capital Advisory Analysis" in cap_res.answer
        assert cap_res.capital_advisory is not None

        # Live Coach mode
        coach_res = await service.process_query(
            AIQueryRequest(query="What is happening right now?", mode="Live Coach")
        )
        assert "MCX Gold Mini" in coach_res.answer

        # Gold Analyst mode
        gold_res = await service.process_query(
            AIQueryRequest(query="What supports this Gold move?", mode="Gold Analyst")
        )
        assert "XAUUSD" in gold_res.answer
        assert "A04" in gold_res.answer

    asyncio.run(_test())
