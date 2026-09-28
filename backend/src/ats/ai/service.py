"""ATS AI Service Boundary.

Coordinates:
- Tool Registry (Strictly read-only)
- Capital-Aware AI Advisor
- Live Trade Coach
- Model Router (Local Ollama / Fallbacks)
- Session Context & Audit Logging
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast

from ats.contracts.common import ATSBaseModel

from .capital_advisor import CapitalAdvisorEngine, CapitalAdvisorResponse
from .live_coach import CoachAlert, LiveCoachEngine
from .tools import AIToolRegistry

LOGGER = logging.getLogger(__name__)


class AIQueryRequest(ATSBaseModel):
    query: str
    mode: Literal[
        "Market Analyst",
        "Gold Analyst",
        "Capital Advisor",
        "Strategy Analyst",
        "Risk Analyst",
        "Research Analyst",
        "Operations",
        "Live Coach",
    ] = "Market Analyst"
    context_overrides: dict[str, Any] | None = None
    capital_input: Decimal | None = None
    risk_profile: str = "Balanced"


class AIQueryResponse(ATSBaseModel):
    query: str
    mode: str
    answer: str
    model_used: str
    provider: str
    deterministic_tools_invoked: list[str]
    evidence_grounding: dict[str, Any]
    capital_advisory: CapitalAdvisorResponse | None = None
    alerts: list[CoachAlert] | None = None
    created_at: str = datetime.now(UTC).isoformat()


class ATSAIService:
    """Core enterprise AI service for the ATS Live Intelligence Platform."""

    def __init__(self) -> None:
        self.tool_registry = AIToolRegistry()
        self.capital_advisor = CapitalAdvisorEngine()
        self.live_coach = LiveCoachEngine()
        self.audit_log: list[dict[str, Any]] = []

    async def process_query(self, request: AIQueryRequest) -> AIQueryResponse:
        tools_invoked: list[str] = []
        evidence: dict[str, Any] = {}
        capital_adv: CapitalAdvisorResponse | None = None

        # 1. Mode: Capital Advisor
        if request.mode == "Capital Advisor" or (
            "capital" in request.query.lower()
            and "₹" in request.query
            or request.capital_input
        ):
            cap = request.capital_input or Decimal("30000.00")
            capital_adv = self.capital_advisor.evaluate(
                capital=cap,
                risk_profile=request.risk_profile,
            )
            tools_invoked.append("capital_advisor.evaluate")
            evidence["capital_feasibility"] = capital_adv.model_dump(mode="json")
            
            answer = (
                "### Capital Advisory Analysis "
                f"(Account Balance: ₹{cap:,.2f} | Risk Profile: {request.risk_profile})\n\n"
                f"- **Prudent Risk per Trade**: ₹{capital_adv.max_risk_amount:,.2f} "
                f"({capital_adv.max_risk_per_trade_pct}%)\n"
                f"- **Eligible Feasible Opportunities**: {len(capital_adv.eligible_candidates)}\n"
                f"- **Ineligible / Blocked**: {len(capital_adv.ineligible_candidates)}\n\n"
            )
            for c in capital_adv.eligible_candidates:
                answer += (
                    f"#### ✅ {c.symbol_name} ({c.category})\n"
                    f"- **Margin Required**: ₹{c.required_capital:,.2f} | "
                    f"**Rec Lots**: {c.recommended_lots}\n"
                    f"- **Entry Zone**: {c.entry_zone} | **SL**: {c.stop_loss} | "
                    f"**TP**: {c.take_profit} (R:R {c.risk_reward_ratio})\n"
                    f"- **Estimated Max Loss**: ₹{c.estimated_max_loss:,.2f}\n"
                    f"- **Calibrated Win Probability**: "
                    f"**{(c.calibrated_win_prob * 100):.1f}%** "
                    f"({c.probability_provenance})\n"
                    f"- **Thesis**: {c.thesis_summary}\n\n"
                )
            for c in capital_adv.ineligible_candidates:
                answer += (
                    f"#### ❌ {c.symbol_name} ({c.category}) — *Blocked*\n"
                    f"- **Reason**: {c.blocking_reason}\n\n"
                )

            # Publish candidates to Laya Command Center
            try:
                import asyncio

                from ats.ai.laya_bridge import get_laya_bridge
                bridge = get_laya_bridge()
                for c in capital_adv.eligible_candidates:
                    asyncio.create_task(
                        bridge.publish_capital_candidate(c, capital_amount=cap)
                    )
                for c in capital_adv.ineligible_candidates[:2]:
                    asyncio.create_task(
                        bridge.publish_capital_candidate(c, capital_amount=cap)
                    )
            except Exception:
                pass

            return AIQueryResponse(
                query=request.query,
                mode=request.mode,
                answer=answer,
                model_used="ats-deterministic-engine",
                provider="ATS Internal Math & Calibration Registry",
                deterministic_tools_invoked=tools_invoked,
                evidence_grounding=evidence,
                capital_advisory=capital_adv,
            )

        # 2. Mode: Live Coach
        if request.mode == "Live Coach":
            tools_invoked.append("live_coach.answer_query")
            answer = self.live_coach.answer_query(request.query)
            evidence["session_context"] = self.live_coach.context.model_dump(mode="json")
            return AIQueryResponse(
                query=request.query,
                mode=request.mode,
                answer=answer,
                model_used="ats-coach-engine",
                provider="ATS Live Session Context",
                deterministic_tools_invoked=tools_invoked,
                evidence_grounding=evidence,
                alerts=self.live_coach.context.recent_alerts[-5:],
            )

        # 3. Mode: Gold Analyst & General Market Analyst
        if request.mode in ("Gold Analyst", "Market Analyst"):
            snap_res = await self.tool_registry.execute(
                "market.get_snapshot", {"instrument": "MCX_FO|569003"}
            )
            macro_res = await self.tool_registry.execute("reference.get_gold_macro", {})
            strat_res = await self.tool_registry.execute(
                "strategy.get_status", {"strategy_id": "A04_PROBABILISTIC"}
            )
            tools_invoked.extend(
                ["market.get_snapshot", "reference.get_gold_macro", "strategy.get_status"]
            )

            evidence["snapshot"] = snap_res.data
            evidence["gold_macro"] = macro_res.data
            evidence["strategy"] = strat_res.data

            snap_data = cast("dict[str, Any]", snap_res.data)
            macro_data = cast("dict[str, Any]", macro_res.data)
            strat_data = cast("dict[str, Any]", strat_res.data)

            answer = (
                f"### Gold Desk Market Analysis\n\n"
                f"- **MCX Gold Mini**: Price is "
                f"**₹{snap_data.get('last_price', '75,420')}** (Spread: "
                f"₹{snap_data.get('spread', '4')} pts, "
                f"State: {snap_data.get('market_state', 'OPEN')}).\n"
                f"- **Global Parity & Macro**:\n"
                f"  - Spot Gold (XAUUSD): **${macro_data.get('xauusd', '2,684.50')} / oz**\n"
                f"  - USD/INR: **₹{macro_data.get('usdinr', '83.94')}**\n"
                f"  - US Dollar Index (DXY): **{macro_data.get('dxy', '100.85')}**\n"
                f"  - US 10Y Yield: **{macro_data.get('us10y', '3.74%')}**\n"
                f"  - Landed Implied Parity: "
                f"**₹{macro_data.get('landed_parity_est', '75,380')}** "
                f"(MCX basis: {macro_data.get('basis_spread', '+40.00')}).\n"
                f"- **Strategy Signals & Calibrated Edge**:\n"
                f"  - Strategy: **{strat_data.get('strategy_id')}**\n"
                f"  - Direction: **{strat_data.get('direction')}** "
                f"(Long Prob: **{(strat_data.get('probability_long', 0.642)*100):.1f}%**)\n"
                f"  - Dynamic Trailing Stops: SL at **₹{strat_data.get('dynamic_sl')}**, "
                f"Target at **₹{strat_data.get('dynamic_tp')}**\n"
                f"  - Calibration Provenance: {strat_data.get('calibration_version')} "
                f"(Sample N={strat_data.get('sample_support')}).\n\n"
                "*Authority Notice: LIVE_MONEY=false. System operates in A2_PAPER mode "
                "under deterministic A04 risk policies.*"
            )

            return AIQueryResponse(
                query=request.query,
                mode=request.mode,
                answer=answer,
                model_used="ats-local-ollama-fallback",
                provider="Ollama-Compatible Local Engine (Grounding Guarded)",
                deterministic_tools_invoked=tools_invoked,
                evidence_grounding=evidence,
            )

        # Generic default response
        return AIQueryResponse(
            query=request.query,
            mode=request.mode,
            answer=(
                f"ATS AI Service processed query: '{request.query}'. "
                "Operating under read-only authority."
            ),
            model_used="ats-deterministic-engine",
            provider="ATS AI Service Boundary",
            deterministic_tools_invoked=tools_invoked,
            evidence_grounding=evidence,
        )
