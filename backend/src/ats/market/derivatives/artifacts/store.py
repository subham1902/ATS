"""Write-once raw artifact store with deterministic hashing and no credential fields."""

from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Lock

from ats.contracts.hashing import canonical_json_bytes

from .models import RawArtifactMetadata, StoredRawArtifact


class ArtifactConflictError(RuntimeError):
    pass


class RawArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._lock = Lock()

    def store(self, *, metadata: RawArtifactMetadata, content: bytes) -> StoredRawArtifact:
        digest = hashlib.sha256(content).hexdigest()
        content_path = self._root / f"{metadata.artifact_id}.raw"
        metadata_path = self._root / f"{metadata.artifact_id}.metadata.json"
        result = StoredRawArtifact(
            metadata=metadata,
            raw_sha256=digest,
            content_length=len(content),
            content_path=str(content_path),
            metadata_path=str(metadata_path),
        )
        with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            if content_path.exists():
                existing = content_path.read_bytes()
                if hashlib.sha256(existing).hexdigest() != digest:
                    raise ArtifactConflictError(
                        "logical artifact already exists with different immutable bytes"
                    )
                if not metadata_path.exists():
                    raise ArtifactConflictError("artifact metadata sidecar is missing")
                return StoredRawArtifact.model_validate_json(metadata_path.read_bytes())
            content_path.write_bytes(content)
            metadata_path.write_bytes(canonical_json_bytes(result))
        return result


__all__ = ["ArtifactConflictError", "RawArtifactStore"]
