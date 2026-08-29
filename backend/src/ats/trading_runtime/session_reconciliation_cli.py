"""Operator CLI for check-only or explicitly authorized stale-state archive."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path

from ats.trading_runtime.session_reconciliation import archive_stale_state, reconcile_launcher_state


def _pid_alive(pid: int) -> bool:
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def _port_active(port: int) -> bool:
    with socket.socket() as client:
        client.settimeout(0.1)
        return client.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--archive-stale", action="store_true")
    args = parser.parse_args()
    state_root = Path(os.environ.get("TEMP", ".")) / "ats-a2-live-paper"
    checkpoint = os.environ.get("ATS_A2_RUNTIME_CHECKPOINT_PATH")
    result = reconcile_launcher_state(
        state_root / "processes.json",
        evidence_root=Path("data/runtime/sessions").resolve(),
        checkpoint_path=Path(checkpoint) if checkpoint else None,
        pid_alive=_pid_alive,
        port_active=_port_active,
    )
    if args.archive_stale:
        result = archive_stale_state(result, archive_root=state_root / "archived" / "stale")
    print(json.dumps(result.__dict__, indent=2, default=str))
    raise SystemExit(
        0 if result.safe_to_archive or result.state.value == "CLEAN_NO_PRIOR_SESSION" else 3
    )


if __name__ == "__main__":
    main()
