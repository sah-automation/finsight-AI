"""Auto-extracted helper for AuroraPgVectorWrite.upsert."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from .aurora_pg_vector_write import (
    _text,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


async def _upsert(
    self: AuroraPgVectorWrite, company_id: CompanyId, *args: Any, **kwargs: Any
) -> int:
    """Alias that accepts either ``(company, version, chunks=..., vectors=...)``
    or ``(company, chunks, vectors)`` so callers can use either shape."""
    version_id = kwargs.pop('version_id', None)
    chunks = kwargs.get('chunks')
    vectors = kwargs.get('vectors', kwargs.get('embeddings'))
    rest = list(args)
    if rest and isinstance(rest[0], str) and version_id is None:
        version_id = rest.pop(0)
    if chunks is None and rest:
        chunks = rest.pop(0)
    if vectors is None and rest:
        vectors = rest.pop(0)
    if chunks is None:
        raise ValueError('chunks are required for a vector write')
    if version_id is None:
        version_id = getattr(chunks[0], 'version_id', None) if chunks else None
    return await self.upsert_chunks(
        company_id,
        _text(version_id),
        chunks=chunks,
        vectors=vectors,
        **kwargs,
    )
