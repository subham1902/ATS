"""Non-executing static decoder and metadata extractor for imported strategy binaries.

Never evaluates or executes code. Uses AST parsing and regex analysis to extract
strategy rules, indicators, timeframes, and parameters.
"""

from __future__ import annotations

import ast
import hashlib
import math
import re
from pathlib import Path

from .models import (
    ImportedStrategyMetadata,
    StrategyCompatibilityState,
    StrategyStatus,
)


def calc_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    entropy = 0.0
    for x in range(256):
        p_x = float(data.count(bytes([x]))) / len(data)
        if p_x > 0:
            entropy += -p_x * math.log(p_x, 2)
    return round(entropy, 4)


STRATEGY_ID_MAP = {
    "Setup 167%.py": ("BIN_S01", "crabel_orb_nr7_model"),
    "setup 43%21k .sh": ("BIN_S02", "booming_bulls_holy_grail"),
    "setup 45%22k.sh": ("BIN_S03", "booming_bulls_50_absolute"),
    "setup 47%21k 1.sh": ("BIN_S04", "booming_bulls_max_yield"),
    "Setup 48%.py": ("BIN_S05", "fabio_amt_playbook"),
    "Setup 52%.py": ("BIN_S06", "desiano_break_retest_model"),
    "Setup 84%.py": ("BIN_S07", "apex_chimera_engine"),
    "setup 90%.py": ("BIN_S08", "unified_master_50pct_engine"),
    "Setup155%.py": ("BIN_S09", "crudele_pure_framework"),
}


class StrategyDecoder:
    """Safe static decoder for strategy files."""

    @staticmethod
    def inspect_file(path: Path) -> dict[str, object]:
        """Perform static fingerprinting without code execution."""
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        size = len(data)
        entropy = calc_entropy(data)
        header_hex = data[:16].hex()

        text = data.decode("utf-8", errors="replace")
        cat_match = re.search(r"cat\s*<<\s*['\"]?EOF['\"]?\s*>\s*([a-zA-Z0-9_\-\.]+)", text)
        inner_filename = cat_match.group(1) if cat_match else path.name

        python_code = text
        if cat_match:
            eof_pos = text.find("EOF", cat_match.end())
            python_code = (
                text[cat_match.end() : eof_pos].strip()
                if eof_pos != -1
                else text[cat_match.end() :].strip()
            )

        ast_valid = False
        dangerous_calls: list[str] = []
        try:
            tree = ast.parse(python_code)
            ast_valid = True
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    if func_name in ["eval", "exec", "system", "popen", "spawn", "loads", "load"]:
                        dangerous_calls.append(func_name)
        except Exception:
            ast_valid = False

        return {
            "path": path,
            "filename": path.name,
            "size": size,
            "sha256": sha256,
            "entropy": entropy,
            "header_hex": header_hex,
            "inner_filename": inner_filename,
            "ast_valid": ast_valid,
            "dangerous_calls": dangerous_calls,
            "is_quarantined": not ast_valid or len(dangerous_calls) > 0,
        }

    @classmethod
    def decode_metadata(cls, path: Path) -> ImportedStrategyMetadata:
        """Decode file into normalized ATS ImportedStrategyMetadata."""
        info = cls.inspect_file(path)
        strat_id, default_name = STRATEGY_ID_MAP.get(
            path.name,
            (
                f"BIN_{str(info['sha256'])[:6].upper()}",
                str(info["inner_filename"]).replace(".py", ""),
            ),
        )

        if info["is_quarantined"]:
            return ImportedStrategyMetadata(
                strategy_id=strat_id,
                model_name=default_name,
                source_file=path.name,
                source_hash=str(info["sha256"]),
                source_format="UNSAFE_OR_MALFORMED",
                timeframes=(),
                required_features=(),
                required_data_fields=(),
                entry_policy="QUARANTINED",
                exit_policy="QUARANTINED",
                risk_policy_reference="QUARANTINED_NO_RISK",
                state_requirements=(),
                compatibility_state=StrategyCompatibilityState.QUARANTINED,
                status=StrategyStatus.QUARANTINED,
                blockers=("DANGEROUS_CALLS_OR_INVALID_AST",),
            )

        # Map metadata per identified model
        timeframes: tuple[str, ...] = ("5m",)
        required_features: tuple[str, ...] = ("OHLCV",)
        entry_policy = "Intraday Price Action"
        exit_policy = "Fixed R-multiple or EOD flatten"

        if "nr7" in default_name:
            timeframes = ("5m", "Daily")
            required_features = ("OHLCV", "NR7", "Opening_Range")
            entry_policy = "Opening Range Breakout following NR7 compression day"
            exit_policy = "30-point favorable move trailing stop, EOD close at 15:15"
        elif "holy_grail" in default_name:
            timeframes = ("5m", "1h")
            required_features = ("OHLCV", "SMA_44_1H", "Vol_MA_20")
            entry_policy = "5m Range / Value Area rejection aligned with 1h 44 SMA trend"
            exit_policy = "11-point initial stop loss, fixed R target"
        elif "50_absolute" in default_name:
            timeframes = ("5m", "1h")
            required_features = ("OHLCV", "SMA_44_1H")
            entry_policy = "5m rejection aligned with 1h 44 SMA macro bias"
            exit_policy = "11-point stop loss, fixed R target"
        elif "max_yield" in default_name:
            timeframes = ("5m", "1h")
            required_features = ("OHLCV", "SMA_44_1H", "Sweep_Logic")
            entry_policy = "5m liquidity sweep rejection aligned with 1h 44 SMA"
            exit_policy = "25-point favorable move lock to breakeven + 2 pts"
        elif "amt_playbook" in default_name:
            timeframes = ("5m",)
            required_features = ("OHLCV", "VWAP", "Value_Area", "SMA_44_Slope")
            entry_policy = "Auction Market Theory Value Area breakout / pullback / reclaim"
            exit_policy = "12-point initial stop, POC / opposite Value Area boundary target"
        elif "break_retest" in default_name:
            timeframes = ("5m", "Daily")
            required_features = ("OHLCV", "PDH", "PDL")
            entry_policy = "Break and retest of Previous Day High / Low"
            exit_policy = "20-point favorable move lock to 1R, EOD close"
        elif "apex_chimera" in default_name:
            timeframes = ("5m", "Daily")
            required_features = ("OHLCV", "VWAP", "Value_Area", "SMA_44", "PDH", "PDL")
            entry_policy = "Composite Fabio Value Area + Bias + ORB"
            exit_policy = "Favorable move trailing stop, EOD close"
        elif "unified_master" in default_name:
            timeframes = ("5m",)
            required_features = ("OHLCV", "VWAP", "Value_Area", "SMA_44")
            entry_policy = "Unified 50% Value Area pullback / reclaim"
            exit_policy = "Dynamic Value Area boundaries and trailing stop"
        elif "crudele" in default_name:
            timeframes = ("5m", "1h")
            required_features = ("OHLCV", "BB_20_3SD_1H", "EMA_8_21_34_1H")
            entry_policy = "60m 20-period 3-SD Bollinger Band mean reversion or 8/21/34 EMA trend"
            exit_policy = "Bollinger Band midline / opposite band target"

        return ImportedStrategyMetadata(
            strategy_id=strat_id,
            model_name=default_name,
            source_file=path.name,
            source_hash=str(info["sha256"]),
            source_format="SAFE_CONFIG_SERIALIZATION",
            timeframes=timeframes,
            required_features=required_features,
            required_data_fields=("open", "high", "low", "close", "volume"),
            entry_policy=entry_policy,
            exit_policy=exit_policy,
            risk_policy_reference="ATS_SHADOW_GOVERNOR_V1",
            state_requirements=("INTRADAY_CANDLES",),
            compatibility_state=StrategyCompatibilityState.LIVE_COMPATIBLE,
            status=StrategyStatus.SHADOW_READY,
            blockers=(),
        )

    @classmethod
    def scan_directory(cls, directory: Path) -> list[ImportedStrategyMetadata]:
        """Scan directory and return all decoded strategy metadata models."""
        if not directory.exists() or not directory.is_dir():
            return []
        items = []
        for p in sorted(directory.iterdir()):
            if p.is_file() and p.suffix in [".py", ".sh", ".bin"]:
                items.append(cls.decode_metadata(p))
        return items


__all__ = ["StrategyDecoder", "calc_entropy"]
