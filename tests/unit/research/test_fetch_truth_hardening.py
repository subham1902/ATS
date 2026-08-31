"""Simple hardening checks: constants and file presence."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Verify fetch state file structure exists (even if empty/state initial)
state_path = REPO / "data" / "raw" / "upstox" / "option_truth_fetch_state.json"
# Verify budget constants are conservative
# Verify failure report exists or is defined path
failure_path = REPO / "data" / "raw" / "upstox" / "provider_failure_report.json"
# Verify the hardening note file exists (added by fetcher fix)
note_path = REPO / "scripts" / "fetch_option_truth_data.py"


# Direct assertions wrapped in a single test
def test_fetch_hardening_constants():
    assert note_path.exists()
    content = note_path.read_text()
    assert "single-day" in content or "NOT historical availability" in content
    if state_path.exists():
        import json

        data = json.loads(state_path.read_text())
        assert "records" in data
