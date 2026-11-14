"""Auto-extracted helper for PostgresChunkRepository.upsert_chunks."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_chunk_repository_shared import (
    _chunk_params,
    _embedding_map,
    _row_to_chunk,
    _upsert_sql,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.core.types import CompanyId
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


async def _upsert_chunks(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    chunks: Sequence[Chunk],
    **kwargs: object,
) -> list[Chunk]:
    company_key = str(company_id)
    if self._session is None:
        return self._upsert_memory(company_key, chunks)
    await self._set_rls_context(company_id)
    embeddings = _embedding_map(kwargs, chunks)
    saved: list[Chunk] = []
    for chunk in chunks:
        row = _chunk_params(company_key, chunk, embeddings)
        result = await self._execute(_upsert_sql(row), row)
        saved.append(_row_to_chunk(await self._fetchone(result)) or chunk)
    return saved
