"""Auto-extracted helper for PostgresChunkRepository._upsert_memory."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.domain.entities.chunk import Chunk

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


def _upsert_memory(
    self: PostgresChunkRepository, company_id: str, chunks: Sequence[Chunk]
) -> list[Chunk]:
    store = self._memory.setdefault(company_id, {})
    saved: list[Chunk] = []
    for chunk in chunks:
        if str(chunk.company_id) != company_id:
            raise ValueError('chunk company_id must match the repository tenant')
        store[str(chunk.chunk_id)] = chunk
        saved.append(chunk)
    return saved
