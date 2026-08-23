"""Opaque UUID conventions and deterministic test-fixture identity support."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID, uuid4, uuid5

from pydantic import Strict

OpaqueId: TypeAlias = Annotated[UUID, Strict()]

# Stable namespace reserved solely for deterministic ATS test fixtures.
ATS_FIXTURE_NAMESPACE = UUID("b0d4c21e-0bcb-5ab6-b93e-35d0bb33bc69")


def new_opaque_id() -> UUID:
    """Create a nondeterministic opaque production identity."""

    return uuid4()


def fixture_id(identity: str, *, namespace: UUID = ATS_FIXTURE_NAMESPACE) -> UUID:
    """Derive a stable UUIDv5 for a non-empty, exact fixture identity string."""

    if not isinstance(identity, str) or not identity:
        raise ValueError("fixture identity must be a non-empty string")
    return uuid5(namespace, identity)


__all__ = ["ATS_FIXTURE_NAMESPACE", "OpaqueId", "fixture_id", "new_opaque_id"]
