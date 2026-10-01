"""Architecture completeness: every production source file has exactly one owner.

``ownership.json`` is architecture metadata (which stream a source area belongs
to), not GitHub CODEOWNERS approval semantics. This test fails when a new
top-level package appears without being assigned, or when two boundaries claim
the same file.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "backend" / "src" / "ats"


def _boundaries() -> list[tuple[str, str, list[str]]]:
    manifest = json.loads((ROOT / "ownership.json").read_text(encoding="utf-8"))
    return [(b["name"], b["owner_stream"], b["paths"]) for b in manifest["boundaries"]]


def _matches(pattern: str, relative: str) -> bool:
    if pattern.endswith("/**"):
        return relative.startswith(pattern[:-2])
    return relative == pattern


def _production_files() -> list[str]:
    return sorted(
        path.relative_to(ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _owners(relative: str) -> list[str]:
    return [
        name
        for name, _stream, patterns in _boundaries()
        if any(_matches(pattern, relative) for pattern in patterns)
    ]


def test_every_production_source_file_belongs_to_a_boundary():
    unowned = [f for f in _production_files() if not _owners(f)]
    assert not unowned, f"unowned source files (assign them in ownership.json): {unowned[:10]}"


def test_no_source_file_belongs_to_multiple_boundaries():
    ambiguous = {f: _owners(f) for f in _production_files() if len(_owners(f)) > 1}
    assert not ambiguous, f"ambiguous ownership: {dict(list(ambiguous.items())[:5])}"


def test_unknown_top_level_packages_fail():
    packages = sorted(
        p.name for p in SOURCE_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"
    )
    claimed = {
        pattern.removeprefix("backend/src/ats/").removesuffix("/**")
        for _name, _stream, patterns in _boundaries()
        for pattern in patterns
        if pattern.startswith("backend/src/ats/") and pattern.endswith("/**")
    }
    assert set(packages) <= claimed, f"unassigned packages: {sorted(set(packages) - claimed)}"


def test_every_boundary_pattern_matches_something():
    files = _production_files()
    stale = []
    for name, _stream, patterns in _boundaries():
        for pattern in patterns:
            if not pattern.startswith("backend/src/ats/"):
                continue  # frontend/tests/benchmarks are outside the Python source root
            if not any(_matches(pattern, f) for f in files):
                stale.append(f"{name}: {pattern}")
    assert not stale, f"ownership entries matching no source (stale): {stale}"
