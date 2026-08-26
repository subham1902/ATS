"""Keep the pinned local DeepSeek Harness ACP process alive behind a health probe."""

from __future__ import annotations

import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ats.intelligence.harness import AcpSubprocessSidecar, HarnessRuntimeConfiguration

_COMMIT = "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"


class _Handler(BaseHTTPRequestHandler):
    sidecar: AcpSubprocessSidecar

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        healthy = self.sidecar.healthy()
        body = json.dumps(
            {
                "status": "HEALTHY" if healthy else "DEGRADED",
                "version": "0.1.1-rc.2",
                "authority": "ADVISORY_ONLY",
            },
            separators=(",", ":"),
        ).encode()
        self.send_response(200 if healthy else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def _configuration(root: Path, node: Path) -> HarnessRuntimeConfiguration:
    actual = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if actual != _COMMIT:
        raise RuntimeError("HARNESS_COMMIT_MISMATCH")
    binary = root / "packages" / "examples" / "acp-demo" / "lib" / "bin.js"
    config = root / "examples" / "acp-agent" / "cordis.yml"
    if not binary.is_file() or not config.is_file():
        raise RuntimeError("HARNESS_BUILD_MISSING")
    return HarnessRuntimeConfiguration(
        source_url="https://github.com/deepseek-ai/deepseek-harness",
        source_tag="dsh-v0.1.1-rc.2",
        source_commit=_COMMIT,
        license="MIT",
        command=(str(node), str(binary), "--config", str(config)),
        cwd=str(root),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness-root", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    configuration = _configuration(args.harness_root, args.node)
    if args.check_config:
        print(json.dumps({"status": "CONFIG_VALID", "version": "0.1.1-rc.2"}))
        return 0
    sidecar = AcpSubprocessSidecar(configuration)
    sidecar.start()
    _Handler.sidecar = sidecar
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        sidecar.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
