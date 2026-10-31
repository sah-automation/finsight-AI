"""Auto-extracted helper for PostgresChunkRepository.mark_chunks_inactive."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_chunk_repository_shared import (
    _ACTIVE_COLUMN,
    _TABLE,
    _rowcount,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.core.types import ChunkId, CompanyId


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


async def _mark_chunks_inactive(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    chunk_ids: Sequence[ChunkId],
    **kwargs: object,
) -> int:
    ids = [str(chunk_id) for chunk_id in chunk_ids]
    if not ids:
        return 0
    if self._session is None:
        return self._mark_memory(str(company_id), ids)
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'UPDATE {_TABLE} SET {_ACTIVE_COLUMN} = FALSE, updated_at = now() '
        'WHERE company_id = :company_id AND chunk_id = ANY(:chunk_ids) '
        f'AND {_ACTIVE_COLUMN} = TRUE',
        {'company_id': str(company_id), 'chunk_ids': ids},
    )
    return _rowcount(result, len(ids))
