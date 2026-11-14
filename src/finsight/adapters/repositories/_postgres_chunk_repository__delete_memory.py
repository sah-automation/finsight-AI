"""Auto-extracted helper for PostgresChunkRepository._delete_memory."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


def _delete_memory(self: PostgresChunkRepository, company_id: str, version_id: str) -> int:
    store = self._memory.get(company_id, {})
    doomed = [key for key, chunk in store.items() if chunk.version_id == version_id]
    for key in doomed:
        del store[key]
    return len(doomed)
