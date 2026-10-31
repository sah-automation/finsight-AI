"""Auto-extracted helper for PostgresChunkRepository.get_chunk."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_chunk_repository_shared import (
    _RETURNING,
    _TABLE,
    _row_to_chunk,
)

if TYPE_CHECKING:
    from finsight.core.types import ChunkId, CompanyId
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


async def _get_chunk(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    chunk_id: ChunkId,
    **kwargs: object,
) -> Chunk | None:
    if self._session is None:
        return self._memory.get(str(company_id), {}).get(str(chunk_id))
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'SELECT {_RETURNING} FROM {_TABLE} '
        'WHERE company_id = :company_id AND chunk_id = :chunk_id',
        {'company_id': str(company_id), 'chunk_id': str(chunk_id)},
    )
    return _row_to_chunk(await self._fetchone(result))
