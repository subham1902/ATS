"""Module-level app for uvicorn — live A2 paper stack (PAPER/DISABLED/ADVISORY_ONLY)."""
from scripts.run_live_a2_stack import build_live_app

app, _controller, _hb, _lb, _prov = build_live_app(require_token=False)
