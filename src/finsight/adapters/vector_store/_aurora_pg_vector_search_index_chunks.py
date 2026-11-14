"""Auto-extracted helper for AuroraPgVectorSearch.index_chunks."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._aurora_pg_vector_search_shared import (
    _as_list,
    _company,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )


if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


async def _index_chunks(
    self: AuroraPgVectorSearch,
    company_id: object,
    chunks: Sequence[object],
    *,
    vectors: object = None,
    categories: object = None,
    **kwargs: object,
) -> int:
    """Seed the in-memory store used when no database session is wired."""
    company = _company(company_id)
    vector_values = _as_list(vectors)
    category_values = _as_list(categories)
    stored = self._chunks.setdefault(company, {})
    written = 0
    for index, chunk in enumerate(chunks):
        record = self._record(company, chunk, index, vector_values, category_values)
        if record is None:
            continue
        stored[record['chunk_id']] = record
        written += 1
    return written
