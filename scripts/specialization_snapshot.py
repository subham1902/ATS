"""Recovery snapshot outside the active product; run before legacy deletion."""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "archive/pre-xauusd-mt5-specialization"


def main() -> None:
    inventory = json.loads((ROOT / "ATS_XAUUSD_SPECIALIZATION_INVENTORY.json").read_text(encoding="utf-8"))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    assert head == inventory["baseline_head"], "Baseline changed before recovery marker"
    found = subprocess.run(["git", "rev-parse", "--verify", MARKER], cwd=ROOT, capture_output=True)
    if found.returncode:
        subprocess.run(["git", "tag", "-a", MARKER, "-m", "Recovery baseline before XAUUSD MetaTrader specialization"], cwd=ROOT, check=True)
    resolved = subprocess.check_output(["git", "rev-parse", MARKER + "^{}"], cwd=ROOT).decode().strip()
    assert resolved == head
    destination = ROOT.parent / "recovery" / ("pre-xauusd-metatrader-" + head[:12] + ".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for item in inventory["records"]:
                path = (ROOT / item["path"]).resolve()
                assert path.is_relative_to(ROOT.resolve()), "Archive path escaped product root"
                assert path.name != ".env" and "local-secrets" not in path.parts
                archive.write(path, item["path"])
            archive.write(ROOT / "ATS_XAUUSD_SPECIALIZATION_INVENTORY.json", "inventory.json")
    with zipfile.ZipFile(destination) as archive:
        for item in inventory["records"]:
            digest = hashlib.sha256(archive.read(item["path"])).hexdigest()
            assert digest == item["sha256"], "Snapshot hash mismatch: " + item["path"]
    print(json.dumps({"marker": MARKER, "head": resolved, "snapshot": str(destination), "verified_files": len(inventory["records"])}))


if __name__ == "__main__":
    main()
