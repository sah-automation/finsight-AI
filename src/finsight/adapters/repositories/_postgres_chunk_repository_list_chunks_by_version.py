"""Auto-extracted helper for PostgresChunkRepository.list_chunks_by_version."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_chunk_repository_shared import (
    _ACTIVE_COLUMN,
    _RETURNING,
    _TABLE,
    _rows_to_chunks,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


async def _list_chunks_by_version(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    version_id: str,
    *,
    include_inactive: bool = False,
    **kwargs: object,
) -> list[Chunk]:
    if self._session is None:
        rows = self._memory.get(str(company_id), {}).values()
        return [
            chunk
            for chunk in rows
            if chunk.version_id == str(version_id) and (include_inactive or chunk.is_active)
        ]
    await self._set_rls_context(company_id)
    sql = (
        f'SELECT {_RETURNING} FROM {_TABLE} '
        'WHERE company_id = :company_id AND version_id = :version_id'
    )
    if not include_inactive:
        sql += f' AND {_ACTIVE_COLUMN} = TRUE'
    result = await self._execute(
        sql + ' ORDER BY ordinal ASC',
        {'company_id': str(company_id), 'version_id': str(version_id)},
    )
    return _rows_to_chunks(await self._fetchall(result))
