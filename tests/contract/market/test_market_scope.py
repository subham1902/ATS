from __future__ import annotations

from pathlib import Path


def test_market_replay_source_has_no_forbidden_runtime() -> None:
    roots = (
        Path("backend/src/ats/market/replay"),
        Path("backend/src/ats/market/calendar"),
        Path("backend/src/ats/market/fixtures"),
    )
    source = "\n".join(
        path.read_text(encoding="utf-8").lower() for root in roots for path in root.glob("*.py")
    )
    forbidden = (
        "requests",
        "httpx",
        "socket",
        "yfinance",
        "selenium",
        "playwright",
        "broker",
        "sqlalchemy",
        "psycopg",
        "redis",
        "torch",
        "transformers",
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "subprocess",
    )
    assert not {item for item in forbidden if item in source}
