"""CLI entrypoint for pre-market readiness check."""

import json
import sys

from ats.trading_runtime.readiness import check_pre_market_readiness


def main() -> None:
    synthetic = "--synthetic" in sys.argv
    res = check_pre_market_readiness(
        trading_date="2026-08-31",
        synthetic_mode=synthetic,
    )
    d = res.to_dict()
    print(json.dumps(d, indent=2))
    if not res.ready_for_a2_paper:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
