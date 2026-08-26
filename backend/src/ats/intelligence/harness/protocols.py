"""Transport seam between ATS and an isolated Harness process."""

from __future__ import annotations

from typing import Protocol


class HarnessSidecar(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def healthy(self) -> bool: ...

    def create_session(self, *, cwd: str) -> str: ...

    def prompt(self, *, provider_session_id: str, prompt: str) -> str: ...

    def cancel(self, *, provider_session_id: str) -> None: ...


__all__ = ["HarnessSidecar"]
