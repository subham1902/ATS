"""M010-00 bootstrap smoke tests."""

from __future__ import annotations

import importlib
import json
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_package_namespaces_import() -> None:
    namespaces = (
        "ats",
        "ats.contracts",
        "ats.contracts.common",
        "ats.contracts.domain",
        "ats.contracts.events",
        "ats.kernel",
        "ats.api",
        "ats.market",
        "ats.forecast",
        "ats.kronos_worker",
        "ats.intelligence",
        "ats.execution",
        "ats.portfolio",
        "ats.events",
        "ats.observability",
    )
    for namespace in namespaces:
        assert importlib.import_module(namespace)


def test_repository_metadata_exists() -> None:
    required = (
        ".python-version",
        ".nvmrc",
        "toolchain.json",
        "pyproject.toml",
        "backend/pyproject.toml",
        "package.json",
        "pnpm-workspace.yaml",
        "ownership.json",
        "README.md",
        "uv.lock",
        "pnpm-lock.yaml",
        ".github/workflows/ci.yml",
    )
    assert all((ROOT / relative_path).is_file() for relative_path in required)


def test_ownership_manifest_is_complete() -> None:
    manifest = json.loads((ROOT / "ownership.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    actual = {item["owner_stream"]: set(item["paths"]) for item in manifest["boundaries"]}
    expected = {
        "A": {"backend/src/ats/contracts/**", "backend/src/ats/kernel/**"},
        "B": {
            "backend/src/ats/market/**",
            "backend/src/ats/forecast/**",
            "backend/src/ats/kronos_worker/**",
        },
        "C": {
            "backend/src/ats/execution/**",
            "backend/src/ats/portfolio/**",
            "backend/src/ats/events/**",
        },
        "D": {"backend/src/ats/intelligence/**"},
        "E": {"frontend/**", "backend/src/ats/api/**"},
        "F": {"tests/**", "benchmarks/**", "backend/src/ats/observability/**"},
    }
    assert actual == expected


def test_forbidden_backend_dependencies_are_absent() -> None:
    forbidden = {
        "agentscope",
        "browser-use",
        "deepseek",
        "kafka-python",
        "kronos",
        "langgraph",
        "nats-py",
        "playwright",
        "redis",
        "torch",
    }
    manifests = (ROOT / "pyproject.toml", ROOT / "backend/pyproject.toml")
    declared: set[str] = set()
    for manifest_path in manifests:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        declared.update(item.split("=", 1)[0].lower() for item in manifest["project"]["dependencies"])
        for group in manifest.get("dependency-groups", {}).values():
            declared.update(item.split("=", 1)[0].lower() for item in group)
    assert declared.isdisjoint(forbidden)


def test_forbidden_frontend_dependencies_are_absent() -> None:
    forbidden = {
        "agentscope",
        "kafkajs",
        "kronos",
        "langgraph",
        "nats",
        "playwright",
        "redis",
    }
    declared: set[str] = set()
    for manifest_path in (ROOT / "frontend").rglob("package.json"):
        if "node_modules" in manifest_path.parts:
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            declared.update(manifest.get(section, {}))
    assert declared.isdisjoint(forbidden)
