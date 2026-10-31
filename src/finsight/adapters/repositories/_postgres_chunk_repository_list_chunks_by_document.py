"""Auto-extracted helper for PostgresChunkRepository.list_chunks_by_document."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_chunk_repository_shared import (
    _ACTIVE_COLUMN,
    _RETURNING,
    _TABLE,
    _rows_to_chunks,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, DocumentId
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


def _list_chunks_memory(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    document_id: DocumentId,
    version_id: str | None,
    include_inactive: bool,
) -> list[Chunk]:
    rows = self._memory.get(str(company_id), {}).values()
    return [
        chunk
        for chunk in rows
        if chunk.document_id == str(document_id)
        and (version_id is None or chunk.version_id == str(version_id))
        and (include_inactive or chunk.is_active)
    ]


async def _list_chunks_document_sql(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    document_id: DocumentId,
    version_id: str | None,
    include_inactive: bool,
) -> list[Chunk]:
    params: dict[str, Any] = {
        'company_id': str(company_id),
        'document_id': str(document_id),
    }
    sql = (
        f'SELECT {_RETURNING} FROM {_TABLE} '
        'WHERE company_id = :company_id AND document_id = :document_id'
    )
    if version_id is not None:
        sql += ' AND version_id = :version_id'
        params['version_id'] = str(version_id)
    if not include_inactive:
        sql += f' AND {_ACTIVE_COLUMN} = TRUE'
    result = await self._execute(sql + ' ORDER BY ordinal ASC', params)
    return _rows_to_chunks(await self._fetchall(result))


async def _list_chunks_by_document(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    document_id: DocumentId,
    *,
    version_id: str | None = None,
    include_inactive: bool = False,
    **kwargs: object,
) -> list[Chunk]:
    if self._session is None:
        return _list_chunks_memory(self, company_id, document_id, version_id, include_inactive)
    await self._set_rls_context(company_id)
    return await _list_chunks_document_sql(
        self, company_id, document_id, version_id, include_inactive
    )
