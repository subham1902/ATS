"""Assert that safety-critical database tests actually executed in CI.

Why this exists
---------------
The durability suites are guarded by ``pytest.importorskip("psycopg")`` and a
session fixture that skips unless ``ATS_TEST_POSTGRES_DSN`` is set. That is the
correct local-developer behaviour, but in CI it means a missing service, a
missing driver or an unset variable silently converts the highest-stakes tests
in the repository -- capital double-spend races, single-use token consumption,
durable authority persistence, reconciliation -- into green skips.

``-x`` and a zero exit code cannot distinguish "passed" from "never ran". This
script closes that hole by reading the JUnit XML that CI produced and failing
loudly when a critical suite was skipped, missing, or produced no tests.

Usage
-----
    python scripts/ci/assert_critical_tests_ran.py junit.xml
    python scripts/ci/assert_critical_tests_ran.py junit1.xml junit2.xml --strict-names
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Each entry is a substring of the JUnit ``classname`` (the test file path).
# Add here any suite whose absence must fail the build -- never delete one
# without replacing the safety property it protected.
CRITICAL_SUITES: tuple[str, ...] = (
    # double-spend / concurrent capital reservation
    "test_capital_reservation_race",
    # durable capital reservation lifecycle
    "test_capital_reservations",
    # event store + payload-hash revalidation on read
    "test_postgres_store",
    # single-use autonomy token: atomic issue/consume, replay impossibility
    "test_reduction_authority_postgres",
    # R17 durable authority evidence rows
    "test_reduction_authority_evidence",
    # D074 recovery / reconciliation after restart
    "test_d074_postgres_recovery",
    # R17 execution journal
    "test_d06_r17_journal",
    # portfolio authority under Postgres transactions
    "test_d05_postgres_actor",
    # position authority durability
    "test_position_authority_postgres",
)


def _iter_testcases(root: ET.Element) -> list[ET.Element]:
    return list(root.iter("testcase"))


def _suite_key(element: ET.Element) -> str:
    """Return the test file identity for a testcase element."""
    classname = element.get("classname") or ""
    name = element.get("name") or ""
    # pytest --junitxml emits classname as the dotted module/path; fall back to
    # the node id so a rename cannot make a suite silently unmatchable.
    return f"{classname} {name}"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    xml_paths = [Path(a) for a in argv[1:] if not a.startswith("--")]
    strict_names = "--strict-names" in argv

    if not xml_paths:
        print("error: no JUnit XML files supplied", file=sys.stderr)
        return 2

    cases: list[ET.Element] = []
    for path in xml_paths:
        if not path.exists():
            print(f"error: JUnit XML not found: {path}", file=sys.stderr)
            return 2
        try:
            cases.extend(_iter_testcases(ET.parse(path).getroot()))
        except ET.ParseError as exc:  # pragma: no cover - defensive
            print(f"error: could not parse {path}: {exc}", file=sys.stderr)
            return 2

    if not cases:
        print("error: JUnit XML contained zero test cases", file=sys.stderr)
        return 2

    failures: list[str] = []

    for suite in CRITICAL_SUITES:
        matching = [c for c in cases if suite in _suite_key(c)]
        if not matching:
            failures.append(f"{suite}: NO TEST CASES FOUND (suite absent from report)")
            continue
        skipped = [c for c in matching if c.find("skipped") is not None]
        errored = [c for c in matching if c.find("error") is not None]
        if skipped:
            reason = skipped[0].find("skipped")
            detail = (reason.get("message") or "").strip() if reason is not None else ""
            failures.append(
                f"{suite}: {len(skipped)}/{len(matching)} SKIPPED -- {detail or 'no reason given'}"
            )
        if errored:
            failures.append(f"{suite}: {len(errored)} ERROR(s)")
        executed = len(matching) - len(skipped)
        print(f"  {suite}: {executed}/{len(matching)} executed")

    if strict_names:
        # Sanity: the report must come from the suites we think it came from.
        if not any("persistence" in _suite_key(c) for c in cases):
            failures.append("report does not contain any tests/integration/persistence cases")

    total = len(cases)
    if failures:
        print(
            "\nFAIL: safety-critical database tests did not execute.\n"
            "This is a CI configuration problem, not a product failure -- do NOT\n"
            "delete entries from CRITICAL_SUITES to make this pass.",
            file=sys.stderr,
        )
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"\nOK: all {len(CRITICAL_SUITES)} critical suites executed ({total} test cases total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
