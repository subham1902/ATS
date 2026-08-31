"""Practical checks guarding the M010-00 scope boundary."""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_no_model_artifacts_or_secret_files() -> None:
    forbidden_suffixes = {".bin", ".ckpt", ".onnx", ".pt", ".pth", ".safetensors"}
    forbidden_names = {".env", "credentials.json", "secrets.json"}
    ignored = {".git", ".mypy_cache", ".next", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}
    tracked_candidates = [
        path for path in ROOT.rglob("*") if not ignored.intersection(path.parts)
    ]
    assert not [path for path in tracked_candidates if path.suffix.lower() in forbidden_suffixes]
    assert not [path for path in tracked_candidates if path.name.lower() in forbidden_names]


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
