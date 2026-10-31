"""Auto-extracted helper for AuroraPgVectorSearch.add_chunk."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


async def _add_chunk(
    self: AuroraPgVectorSearch,
    company_id: object,
    chunk: object,
    *,
    vector: object = None,
    **kwargs: object,
) -> int:
    return await self.index_chunks(
        company_id,
        [chunk],
        vectors=[vector] if vector is not None else None,
        categories=kwargs.get('category'),
    )
