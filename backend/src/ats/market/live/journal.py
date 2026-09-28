"""Non-blocking append-only market event journal."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate

LOGGER = logging.getLogger(__name__)


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """Versioned, immutable journal observation."""

    schema_version: str
    provider: str
    instrument_key: str
    event_type: str
    source_timestamp: datetime | None
    received_at: datetime
    last_price: Decimal | None
    volume: int | None
    open_interest: int | None
    bid: Decimal | None
    ask: Decimal | None
    bid_qty: int | None
    ask_qty: int | None
    raw_payload_preview: str | None


class MarketJournal:
    """Asynchronous, bounded, append-only market event journal."""

    def __init__(
        self,
        storage_dir: Path | str = "data/market_journal",
        max_memory_entries: int = 5000,
        provider: str = "upstox",
    ) -> None:
        self.provider = provider
        self.storage_dir = Path(storage_dir)
        self.max_memory_entries = max_memory_entries
        self._memory_queue: deque[JournalEntry] = deque(maxlen=max_memory_entries)
        self._write_queue: asyncio.Queue[JournalEntry] = asyncio.Queue(maxsize=10000)
        self._overflow_count = 0
        self._total_recorded = 0
        self._flush_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def overflow_count(self) -> int:
        return self._overflow_count

    @property
    def total_recorded(self) -> int:
        return self._total_recorded

    @property
    def memory_depth(self) -> int:
        return len(self._memory_queue)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._flush_task = asyncio.create_task(self._background_flush_loop())
        LOGGER.info("MarketJournal started writing to %s", self.storage_dir)

    def stop(self) -> None:
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

    def record(self, update: NormalizedFeedUpdate, raw_preview: str | None = None) -> None:
        """Record an update non-blockingly. Enforces explicit overflow detection."""
        entry = JournalEntry(
            schema_version="2.0",
            provider=self.provider,
            instrument_key=update.instrument_key,
            event_type=update.kind.value if hasattr(update.kind, "value") else str(update.kind),
            source_timestamp=update.exchange_timestamp,
            received_at=update.received_at or datetime.now(UTC),
            last_price=update.last_traded_price,
            volume=update.volume,
            open_interest=update.open_interest,
            bid=update.bid_price,
            ask=update.ask_price,
            bid_qty=update.bid_quantity,
            ask_qty=update.ask_quantity,
            raw_payload_preview=raw_preview,
        )

        self._memory_queue.append(entry)
        self._total_recorded += 1

        try:
            self._write_queue.put_nowait(entry)
        except asyncio.QueueFull:
            self._overflow_count += 1
            LOGGER.warning(
                "MarketJournal queue full! Overflow count=%d. Evicting oldest write record.",
                self._overflow_count,
            )
            try:
                _ = self._write_queue.get_nowait()
                self._write_queue.put_nowait(entry)
            except Exception:
                pass

    def recent_entries(self, limit: int = 100) -> tuple[JournalEntry, ...]:
        return tuple(list(self._memory_queue)[-limit:])

    async def _background_flush_loop(self) -> None:
        """Batch write entries to disk in hourly rotating JSONL logs."""
        batch: list[JournalEntry] = []
        while self._running:
            try:
                # Wait for next item or flush timeout
                try:
                    entry = await asyncio.wait_for(self._write_queue.get(), timeout=1.0)
                    batch.append(entry)
                except TimeoutError:
                    pass

                # Drain available items up to batch size 100
                while not self._write_queue.empty() and len(batch) < 100:
                    batch.append(self._write_queue.get_nowait())

                if batch:
                    await self._flush_batch(batch)
                    batch.clear()

            except asyncio.CancelledError:
                if batch:
                    await self._flush_batch(batch)
                break
            except Exception as e:
                LOGGER.error("Journal flush error: %s", e)
                await asyncio.sleep(1.0)

    async def _flush_batch(self, batch: list[JournalEntry]) -> None:
        now = datetime.now(UTC)
        file_path = self.storage_dir / f"journal_{self.provider}_{now.strftime('%Y%m%d_%H')}.jsonl"
        lines = [json.dumps(asdict(e), default=_decimal_default) + "\n" for e in batch]

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_lines, file_path, lines)

    @staticmethod
    def _write_lines(path: Path, lines: list[str]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.writelines(lines)
