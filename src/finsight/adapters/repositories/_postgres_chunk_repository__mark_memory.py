"""Auto-extracted helper for PostgresChunkRepository._mark_memory."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


def _mark_memory(
    self: PostgresChunkRepository,
    company_id: str,
    chunk_ids: list[str] | None,
    *,
    version_id: str | None = None,
    exclude: list[str] | None = None,
) -> int:
    store = self._memory.get(company_id, {})
    excluded = set(exclude or ())
    changed = 0
    for chunk_id, chunk in store.items():
        if chunk_ids is not None and chunk_id not in chunk_ids:
            continue
        if version_id is not None and chunk.version_id != version_id:
            continue
        if chunk_id in excluded or not chunk.is_active:
            continue
        chunk.mark_inactive()
        changed += 1
    return changed
