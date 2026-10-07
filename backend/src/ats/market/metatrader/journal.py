"""Append observed canonical events before feature distribution."""

from __future__ import annotations

import os
from pathlib import Path

from ats.market.observations import MarketObservation


class ObservationJournal:
    def __init__(self, root: Path) -> None:
        self.root = root

    def append(self, observation: MarketObservation) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / (observation.received_at.strftime("%Y%m%d-%H") + ".jsonl")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(observation.model_dump_json() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
