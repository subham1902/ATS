"""Safe loading of mutable, durable JSON stores.

The failure this exists to prevent: a store file fails to parse, the loader
logs a warning and starts empty, and the next save overwrites the only copy of
the data. For durable evidence or operator state a parse failure must never
become "valid, empty state followed by overwrite".

Use :func:`read_json_or_quarantine`: unreadable bytes are moved aside intact
(``<name>.corrupt-<utc>``) so the original survives, and the caller is told the
store is degraded. If the file cannot even be moved aside, the caller must stop
writing (``blocked=True``) rather than risk clobbering it.

Disposable caches and regenerable artifacts do not need this.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class JsonLoad:
    """Outcome of a guarded load."""

    data: Any = None
    #: True when the file existed but could not be used.
    degraded: bool = False
    #: Where the unreadable original was preserved, if it was moved.
    quarantined_to: Path | None = None
    #: True when the original could neither be parsed nor moved aside; the
    #: caller must not write to the path.
    blocked: bool = False
    reason: str | None = None

    @property
    def missing(self) -> bool:
        return self.data is None and not self.degraded


def quarantine_file(path: Path) -> Path | None:
    """Move ``path`` aside under a unique ``.corrupt-<utc>`` name; ``None`` on failure."""

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    target = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        os.replace(path, target)
    except OSError as exc:
        LOGGER.error("Could not quarantine unreadable store %s: %s", path.name, exc)
        return None
    LOGGER.error("Unreadable store %s preserved as %s; starting degraded", path.name, target.name)
    return target


def quarantine_after_failure(path: Path, reason: str) -> JsonLoad:
    """For callers that parse themselves: preserve the file and report why."""

    moved = quarantine_file(path)
    return JsonLoad(degraded=True, quarantined_to=moved, blocked=moved is None, reason=reason)


def read_json_or_quarantine(path: Path) -> JsonLoad:
    """Load JSON from ``path``.

    * missing file -> ``JsonLoad()`` (``missing``; a normal first run)
    * parses -> ``JsonLoad(data=...)``
    * unreadable/unparseable -> original preserved, ``degraded=True``
    """

    if not path.exists():
        return JsonLoad()
    try:
        return JsonLoad(data=json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        # Log the failure class and position only, never file contents.
        return quarantine_after_failure(path, f"{type(exc).__name__}: {exc}")


__all__ = ["JsonLoad", "quarantine_after_failure", "quarantine_file", "read_json_or_quarantine"]
