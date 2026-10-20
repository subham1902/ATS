"""Static governance gate for the native MetaTrader sources.

The read-only guarantee of `ATSSmallAccountObserver.mq5` is currently enforced
by a comment and by review. This script turns it into a build failure.

It does not compile MQL -- that is `mql-compile`'s job on a Windows runner. It
asserts the invariants that make the observer safe regardless of whether it
compiles: no trading API surface, no command ingress, resolvable includes.

Every finding is fatal. There is deliberately no warning level: a native EA that
has acquired the ability to send an order is not a style problem.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

# Any one of these in a source file means the EA can reach the order subsystem.
FORBIDDEN_TRADE_SYMBOLS: Final[tuple[str, ...]] = (
    "OrderSend",
    "OrderSendAsync",
    "OrderClose",
    "OrderModify",
    "OrderDelete",
    "PositionClose",
    "PositionOpen",
    "PositionModify",
    "CTrade",
    "CPositionInfo",
    "COrderInfo",
    "MqlTradeRequest",
    "MqlTradeResult",
    "MqlTradeCheckResult",
)

FORBIDDEN_INCLUDES: Final[tuple[str, ...]] = (
    "Trade/Trade.mqh",
    "Trade/PositionInfo.mqh",
    "Trade/OrderInfo.mqh",
    "Trade/SymbolInfo.mqh",
    "Expert/Expert.mqh",
)

# Reading a command file is how an EA acquires ingress. The EA README states
# that a command file is intentionally not accepted; this keeps it that way.
COMMAND_INGRESS_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    (r"\bFileOpen\s*\([^)]*FILE_READ(?![^)]*FILE_WRITE)", "reads a file"),
    (r"\bWebRequest\s*\(", "performs an HTTP request"),
    (r"\bSocketCreate\s*\(", "opens a socket"),
    (r"\bSocketConnect\s*\(", "opens a socket"),
    (r"#import\b", "imports an external DLL"),
)

# FileSha256 legitimately reads the clock profile, and nothing else may read.
INGRESS_ALLOWLIST: Final[dict[str, tuple[str, ...]]] = {
    "SmallAccountSignals.mqh": ("FileOpen",),
}

COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
STRING_RE: Final[re.Pattern[str]] = re.compile(r'"(?:[^"\\]|\\.)*"')
# The delimiter is captured: angle-bracket includes belong to the `#ifdef
# __cplusplus` branch these headers carry so the numeric core can be compiled
# and parity-tested on Linux. Only quoted, local includes are resolvable here.
INCLUDE_RE: Final[re.Pattern[str]] = re.compile(r'#include\s+(["<])([^>"]+)[>"]')


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def strip_noise(text: str) -> str:
    """Blank out comments and string literals, preserving line numbering.

    Matching on raw text would flag the word OrderSend inside the very comments
    that promise the EA never calls it.
    """

    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return STRING_RE.sub(blank, COMMENT_RE.sub(blank, text))


def check_source(path: Path, root: Path) -> list[Finding]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = strip_noise(raw)
    lines = code.splitlines()
    findings: list[Finding] = []
    allowed = INGRESS_ALLOWLIST.get(path.name, ())

    for number, line in enumerate(lines, start=1):
        for symbol in FORBIDDEN_TRADE_SYMBOLS:
            if re.search(rf"\b{re.escape(symbol)}\b", line):
                findings.append(
                    Finding(
                        path.relative_to(root),
                        number,
                        "TRADE_API",
                        f"references {symbol}; the observer must have no order path",
                    )
                )
        for pattern, description in COMMAND_INGRESS_PATTERNS:
            if not re.search(pattern, line):
                continue
            token = pattern.split("\\b")[1].split("\\s")[0] if "\\b" in pattern else pattern
            if token in allowed:
                continue
            findings.append(
                Finding(
                    path.relative_to(root),
                    number,
                    "INGRESS",
                    f"{description}; command ingress is intentionally unsupported",
                )
            )

    for number, line in enumerate(lines, start=1):
        match = INCLUDE_RE.search(line)
        if not match:
            continue
        delimiter, target = match.group(1), match.group(2)
        normalised = target.replace("\\", "/")
        if normalised in FORBIDDEN_INCLUDES:
            findings.append(
                Finding(
                    path.relative_to(root),
                    number,
                    "TRADE_INCLUDE",
                    f"includes {target}",
                )
            )
        elif delimiter == '"' and not (path.parent / normalised).exists():
            # A quoted include is local. If it does not resolve, the Windows
            # compile fails later and far more expensively.
            findings.append(
                Finding(
                    path.relative_to(root),
                    number,
                    "MISSING_INCLUDE",
                    f"{target} does not resolve next to {path.name}",
                )
            )
    return findings


def check_structure(path: Path, root: Path) -> list[Finding]:
    """Encoding check only.

    Syntactic well-formedness is proven properly elsewhere: the numeric core is
    compiled by the ziglang C++ parity harness on Linux, and the full EA by
    MetaEditor on the Windows job. Brace counting would false-positive across
    the `#ifdef __cplusplus` branches in the Core headers and prove nothing the
    two real compiles do not.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    findings: list[Finding] = []
    try:
        raw.encode("ascii")
    except UnicodeEncodeError as exc:
        findings.append(
            Finding(
                path.relative_to(root),
                0,
                "ENCODING",
                f"non-ASCII byte at offset {exc.start}; MetaEditor ANSI sources "
                "must stay ASCII",
            )
        )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        default=["metatrader", "connectors"],
        help="directories to scan (default: metatrader connectors)",
    )
    args = parser.parse_args(argv)
    repo = Path.cwd()

    sources: list[Path] = []
    for root in args.roots:
        base = repo / root
        if not base.exists():
            print(f"MQL_GATE_FAILED: {root} does not exist", file=sys.stderr)
            return 1
        for suffix in ("*.mq5", "*.mq4", "*.mqh"):
            sources.extend(sorted(base.rglob(suffix)))

    if not sources:
        print("MQL_GATE_FAILED: no MQL sources found; the gate would pass vacuously",
              file=sys.stderr)
        return 1

    findings: list[Finding] = []
    for source in sources:
        findings.extend(check_source(source, repo))
        findings.extend(check_structure(source, repo))

    print(f"scanned {len(sources)} MQL source file(s)")
    for source in sources:
        print(f"  {source.relative_to(repo)}")

    if findings:
        print(f"\nMQL_GATE_FAILED: {len(findings)} finding(s)", file=sys.stderr)
        for finding in findings:
            print(f"  {finding.render()}", file=sys.stderr)
        return 1

    print("\nread-only invariants hold: no trade API, no command ingress, "
          "includes resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
