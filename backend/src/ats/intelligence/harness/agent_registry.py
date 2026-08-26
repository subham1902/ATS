"""Fixed Harness agent scopes and bounded resource/capability envelopes."""

from __future__ import annotations

from datetime import timedelta

from pydantic import PositiveInt

from ats.contracts.common import ATSBaseModel
from ats.intelligence.agent_governance import AgentToolName

from .models import HarnessAgentType


class HarnessAgentPolicy(ATSBaseModel):
    agent_type: HarnessAgentType
    tools: tuple[AgentToolName, ...]
    context_item_limit: PositiveInt
    timeout: timedelta
    staleness_ttl: timedelta
    maximum_tool_calls: PositiveInt


HARNESS_AGENT_REGISTRY: dict[HarnessAgentType, HarnessAgentPolicy] = {
    HarnessAgentType.SESSION_MARKET: HarnessAgentPolicy(
        agent_type=HarnessAgentType.SESSION_MARKET,
        tools=(
            AgentToolName.GET_MARKET_CONTEXT,
            AgentToolName.GET_LATEST_MARKET_SNAPSHOT,
            AgentToolName.GET_OPTION_WINDOW,
            AgentToolName.GET_CURRENT_RISK_STATE,
            AgentToolName.GET_RECENT_ACTIVITY,
        ),
        context_item_limit=128,
        timeout=timedelta(seconds=20),
        staleness_ttl=timedelta(seconds=15),
        maximum_tool_calls=8,
    ),
    HarnessAgentType.POSITION: HarnessAgentPolicy(
        agent_type=HarnessAgentType.POSITION,
        tools=(
            AgentToolName.GET_POSITION_CONTEXT,
            AgentToolName.GET_MARKET_CONTEXT,
            AgentToolName.GET_CURRENT_RISK_STATE,
            AgentToolName.GET_RECENT_ACTIVITY,
        ),
        context_item_limit=96,
        timeout=timedelta(seconds=15),
        staleness_ttl=timedelta(seconds=10),
        maximum_tool_calls=6,
    ),
    HarnessAgentType.PORTFOLIO_ANALYST: HarnessAgentPolicy(
        agent_type=HarnessAgentType.PORTFOLIO_ANALYST,
        tools=(
            AgentToolName.GET_PORTFOLIO_CONTEXT,
            AgentToolName.GET_CURRENT_RISK_STATE,
            AgentToolName.GET_RECENT_TRADES,
            AgentToolName.GET_PERFORMANCE_ATTRIBUTION,
            AgentToolName.GET_RECENT_ACTIVITY,
        ),
        context_item_limit=128,
        timeout=timedelta(seconds=30),
        staleness_ttl=timedelta(seconds=30),
        maximum_tool_calls=10,
    ),
    HarnessAgentType.RESEARCH: HarnessAgentPolicy(
        agent_type=HarnessAgentType.RESEARCH,
        tools=(
            AgentToolName.GET_STRATEGY_DEFINITION,
            AgentToolName.GET_HISTORICAL_EVIDENCE,
            AgentToolName.GET_EXPERIMENT_STATE,
            AgentToolName.GET_PERFORMANCE_ATTRIBUTION,
            AgentToolName.GET_CAMPAIGN_STATE,
        ),
        context_item_limit=256,
        timeout=timedelta(seconds=60),
        staleness_ttl=timedelta(minutes=5),
        maximum_tool_calls=16,
    ),
}


def policy_for(agent_type: HarnessAgentType) -> HarnessAgentPolicy:
    return HARNESS_AGENT_REGISTRY[agent_type]


__all__ = ["HARNESS_AGENT_REGISTRY", "HarnessAgentPolicy", "policy_for"]
