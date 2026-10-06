"""Engineering inventory; never imports or executes an artifact being audited."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = re.compile(r"upstox|\bnse\b|\bmcx\b|goldm|nifty|banknifty|sensex|\bindia\b|indian|exchange_token|instrument_key|MCX_REGULAR", re.I)
TRUSTED = ("backend/src/ats/contracts/", "backend/src/ats/kernel/", "backend/src/ats/execution/", "backend/src/ats/portfolio/", "backend/src/ats/persistence/", "backend/src/ats/governance/")
DELETE_TREES = ("backend/src/ats/market/feeds/upstox_v3/", "backend/src/ats/market/providers/upstox/", "backend/src/ats/market/data_acquisition/", "backend/src/ats/optimization/", "backend/src/ats/market/strategy_import/")


def main() -> None:
    print("Inventory: enumerating tracked source", flush=True)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    candidates = {ROOT / p for p in tracked if p}
    for relative in ("data", "backend/src/data", "reports", "dist"):
        print(f"Inventory: enumerating {relative}", flush=True)
        candidates.update(p for p in (ROOT / relative).rglob("*") if p.is_file())
    records = []
    print(f"Inventory: hashing {len(candidates)} files", flush=True)
    for path in sorted(candidates):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        # rg supplies the full source scan. Artifact provenance comes from paths
        # and headers; never decode gigabytes of tick payloads as documentation.
        content = raw[:65536].decode("utf-8", errors="ignore")
        matches = sorted(set(m.group().lower() for m in LEGACY.finditer(rel + "\n" + content)))
        state = path.suffix.lower() in {".pkl", ".joblib", ".pt", ".pth", ".onnx", ".bin", ".model", ".db", ".sqlite", ".sqlite3"}
        if rel.startswith(("data/", "backend/src/data/", "reports/")):
            if rel.endswith(".gitkeep"):
                classification, reason = "KEEP GENERIC", "Empty storage boundary; no market evidence."
            elif "managed.json" in rel:
                classification, reason = "REVIEW", "Preserve agent definitions; audit scopes and isolate prior research runs."
            else:
                classification, reason = "DELETE", "Legacy market state" if matches else "PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state."
        elif rel.startswith("dist/") or "__pycache__" in rel:
            classification, reason = "GENERATED/EPHEMERAL", "Rebuild from specialized source."
        elif rel.startswith(DELETE_TREES) or "upstox" in rel.lower():
            classification, reason = "DELETE", "Obsolete provider implementation, fixtures, tests or provider documentation."
        elif rel.startswith(TRUSTED):
            classification, reason = "KEEP GENERIC", "Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary."
        elif "/derivatives/" in rel:
            classification, reason = "REVIEW", "Trace core references; remove acquisition/options logic and replace runtime instrument seam."
        elif matches:
            classification, reason = "REWRITE FOR XAUUSD", "Legacy assumptions or identifiers; retain only useful generic behavior."
        elif "s5" in rel.lower() or "xauusd" in rel.lower():
            classification, reason = "KEEP XAUUSD", "Research definition only; no performance or promotion authority."
        else:
            classification, reason = "KEEP GENERIC", "No legacy reference found; subject to dependency audit."
        records.append({"path": rel, "classification": classification, "reason": reason, "legacy_terms": matches, "serialized_state": state, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    manifest = {"baseline_head": head, "records": records}
    (ROOT / "ATS_XAUUSD_SPECIALIZATION_INVENTORY.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    counts = Counter(r["classification"] for r in records)
    lines = ["# XAUUSD / MT5 specialization inventory", "", f"Baseline: `{head}` on `main`. Actual product root: `D:/Projects/ATS/ats`.", "", "This inventory was produced before deletion. The accompanying JSON records each path, classification, SHA-256, size and matched legacy terms. No serialized model was loaded. REVIEW entries require dependency inspection before deletion.", "", "## Safety and authority", "", "Keep the deterministic contracts/kernel, portfolio authority, durable token consumption and PaperBroker path. No real orders. Remove the startup synthetic tick and all outer-workspace evidence discovery. Existing managed-agent configuration is locally modified and must be recoverable. No performance claim transfers from another market.", "", "## Scope decisions", "", "- External provider: MT5, read-only. Canonical instrument: XAUUSD; broker symbol is configured separately.", "- Upstox raw data, journals, replays, calibration and old strategy scores are deleted after recovery snapshot verification.", "- Unattributed learned/derived state is PROVENANCE_UNKNOWN - NOT ELIGIBLE and cannot initialize the product.", "- S5 becomes XAUUSD-native DESIGN / RESEARCH_ONLY with unresolved decisions retained.", "- Managed research agents survive; the old capital-bearing persona playground is reviewed separately from the managed-agent boundary.", "- Generic strategy definitions may survive; old fitness, promotion and tournament evidence does not.", "- The outer workspace, toolchains and other Git worktrees are recovery/research material outside the active product. The specialized application must never read their old evidence.", "", "## Classification counts", "", "| Classification | Files |", "| --- | ---: |"]
    lines += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    lines += ["", "## Per-file classification", "", "| Path | Classification | Reason |", "| --- | --- | --- |"]
    lines += [f"| `{r['path']}` | {r['classification']} | {r['reason']} |" for r in records]
    (ROOT / "ATS_XAUUSD_SPECIALIZATION_INVENTORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": head, "files": len(records), "classifications": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
