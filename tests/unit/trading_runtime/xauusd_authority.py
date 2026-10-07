"""Synthetic single-instrument capital policy for runtime authority mechanics."""

from decimal import Decimal

from ats.portfolio.runtime import PartitionCapitalLimit

from tests.unit.portfolio.runtime.helpers import policy


def xauusd_policy(*, maximum: int = 2):
    return policy(maximum=maximum).model_copy(
        update={
            "market_limits": (
                PartitionCapitalLimit(partition_key="XAUUSD", maximum_capital=Decimal("300000")),
            )
        }
    )
