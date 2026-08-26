from pathlib import Path

SCRIPTS = Path("scripts")


def test_stack_scripts_pin_release_runtime_and_never_enable_live_money() -> None:
    start = (SCRIPTS / "start_pre_market_stack.ps1").read_text(encoding="utf-8")
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            SCRIPTS / "start_pre_market_stack.ps1",
            SCRIPTS / "stop_pre_market_stack.ps1",
            SCRIPTS / "check_pre_market_stack.ps1",
        )
    ).lower()
    assert "v24.19.0" in start
    assert "11.9.0" in start
    assert "enable live" not in combined
    assert "place_order" not in combined
    assert "modify_order" not in combined
    assert "cancel_order" not in combined


def test_start_uses_hidden_bounded_local_services() -> None:
    source = (SCRIPTS / "start_pre_market_stack.ps1").read_text(encoding="utf-8")
    assert source.count("-WindowStyle Hidden") == 3
    assert "127.0.0.1" in source
    assert "ats.api.app:app" in source
    assert "dsh-v0.1.1-rc.2" not in source  # version is verified by the built pinned source


def test_harness_health_wrapper_pins_exact_source_commit() -> None:
    source = (SCRIPTS / "run_harness_sidecar.py").read_text(encoding="utf-8")
    assert "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e" in source
    assert "ADVISORY_ONLY" in source
    assert "place_order" not in source
