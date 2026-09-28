"""Practical checks guarding the M010-00 scope boundary."""

from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Directories that hold first-party source. Used only when git is unavailable,
# so the scan still targets code rather than local runtime/config noise.
SOURCE_ROOTS = ("backend", "frontend", "tests", "scripts", "docs")


def _repository_paths() -> list[pathlib.Path]:
    """Return every path that can enter this repository.

    The authoritative set is ``git ls-files -co --exclude-standard``: tracked
    files plus untracked files that ``git add`` would stage. This is exactly the
    population a secret or model artifact must never appear in, and it honours
    ``.gitignore`` — which explicitly sanctions local ``.env`` config. A plain
    filesystem walk is both noisier (it fails on legitimate local env files) and
    weaker (it cannot tell repository content from working-directory scratch).

    Falls back to a source-root walk when git is unavailable (source
    distributions, offline sandboxes).
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return [
            path
            for root in SOURCE_ROOTS
            for path in (ROOT / root).rglob("*")
            if path.is_file() and ".git" not in path.parts and "node_modules" not in path.parts
        ]
    return [
        ROOT / entry
        for entry in result.stdout.decode("utf-8", errors="replace").split("\0")
        if entry
    ]


def test_no_model_artifacts_or_secret_files() -> None:
    forbidden_suffixes = {".bin", ".ckpt", ".onnx", ".pt", ".pth", ".safetensors"}
    forbidden_names = {".env", "credentials.json", "secrets.json"}
    candidates = _repository_paths()
    assert candidates, "repository path enumeration returned nothing; refusing to pass vacuously"
    assert not [
        path.relative_to(ROOT) for path in candidates if path.suffix.lower() in forbidden_suffixes
    ], "model artifacts must never be committable"
    assert not [
        path.relative_to(ROOT) for path in candidates if path.name.lower() in forbidden_names
    ], "secret files must never be committable"


def test_no_live_or_credential_implementation_markers() -> None:
    source_roots = (ROOT / "backend" / "src", ROOT / "frontend")
    patterns = (
        re.compile(r"\b(?:api[_-]?key|totp|broker[_-]?token)\s*=\s*[\"']", re.IGNORECASE),
        re.compile(r"\bplace[_-]?order\s*\(", re.IGNORECASE),
        re.compile(r"\benable[_-]?a[345]\b", re.IGNORECASE),
    )
    findings: list[str] = []
    for source_root in source_roots:
        for path in source_root.rglob("*"):
            if "node_modules" in path.parts or ".next" in path.parts:
                continue
            if path.is_file() and path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".json"}:
                text = path.read_text(encoding="utf-8")
                if any(pattern.search(text) for pattern in patterns):
                    findings.append(str(path.relative_to(ROOT)))
    assert not findings
