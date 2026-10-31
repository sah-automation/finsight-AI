"""Auto-extracted helper for PostgresChunkRepository.mark_version_chunks_inactive."""

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


async def _mark_version_chunks_inactive(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    version_id: str,
    *,
    exclude_chunk_ids: Sequence[ChunkId] = (),
    **kwargs: object,
) -> int:
    excluded = [str(chunk_id) for chunk_id in exclude_chunk_ids]
    if self._session is None:
        return self._mark_memory(
            str(company_id), None, version_id=str(version_id), exclude=excluded
        )
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'UPDATE {_TABLE} SET {_ACTIVE_COLUMN} = FALSE, updated_at = now() '
        'WHERE company_id = :company_id AND version_id = :version_id '
        f'AND {_ACTIVE_COLUMN} = TRUE '
        'AND (cardinality(:exclude_ids) = 0 OR NOT (chunk_id = ANY(:exclude_ids)))',
        {
            'company_id': str(company_id),
            'version_id': str(version_id),
            'exclude_ids': excluded,
        },
    )
    return _rowcount(result, 0)
