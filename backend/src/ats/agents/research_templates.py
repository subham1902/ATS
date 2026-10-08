"""Shared proposal-only templates; none is an execution worker."""

TEMPLATES = (
    (
        "Strategy Research Agent",
        "Generate XAUUSD hypotheses and evidence requirements",
        "PROPOSE_STRATEGY",
    ),
    (
        "Backtest Agent",
        "Run approved bounded jobs with dataset, version and cost provenance",
        "RUN_BACKTEST",
    ),
    (
        "Validation Agent",
        "Disprove hypotheses using holdout, leakage and cost stress",
        "RUN_RESEARCH",
    ),
    (
        "Signal Analyst Agent",
        "Report direction, horizon, entry, SL/TP and UNKNOWN probability",
        "ANALYZE_STRATEGY",
    ),
    ("Regime Agent", "Analyze observed XAUUSD regimes", "ANALYZE_STRATEGY"),
    ("SL TP Analyst Agent", "Propose stop and target research", "RISK_RESEARCH"),
    ("Entry Quality Agent", "Analyze versioned entry path evidence", "ANALYZE_STRATEGY"),
    (
        "Exit Watch Agent",
        "Advisories only; request human attention, never close a position",
        "ANALYZE_STRATEGY",
    ),
    ("Trade Forensics Agent", "Explain trade lineage and observed outcomes", "GENERATE_REPORT"),
    ("Strategy Librarian Agent", "Maintain strategy research documentation", "GENERATE_REPORT"),
)


def research_templates() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "purpose": purpose,
            "capabilities": [capability],
            "data_scopes": ["XAUUSD_STRATEGIES", "XAUUSD_RESEARCH"],
            "financial_authority": "NONE",
            "status": "TEMPLATE",
            "system_instructions": (
                "XAUUSD research only. AI proposes; deterministic ATS authorizes. "
                "Never access broker secrets or execution. No dataset/version/cost evidence "
                "means no performance claim. Model confidence is not empirical probability."
            ),
        }
        for name, purpose, capability in TEMPLATES
    ]
