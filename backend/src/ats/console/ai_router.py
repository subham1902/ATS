"""An evidence-grounded research context, without financial authority."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ats.console.market_router import get_market_quote

router = APIRouter(prefix="/v1/ai", tags=["research-assistant"])


class ResearchQuery(BaseModel):
    query: str
    mode: str = "Research Analyst"


@router.post("/query")
def query(request: Request, body: ResearchQuery) -> dict[str, object]:
    return {
        "query": body.query,
        "mode": body.mode,
        "answer": (
            "ATS supports XAUUSD research only. "
            "No repository evidence establishes profitability. "
            "Strategy validation and deterministic A04 authorization "
            "are required before paper execution."
        ),
        "model_used": "deterministic-context",
        "provider": "ATS",
        "deterministic_tools_invoked": ["market.quote"],
        "evidence_grounding": get_market_quote(request),
        "authority": "PROPOSAL_ONLY",
    }
