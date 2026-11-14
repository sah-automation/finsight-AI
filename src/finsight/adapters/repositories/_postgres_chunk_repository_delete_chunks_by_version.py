"""Auto-extracted helper for PostgresChunkRepository.delete_chunks_by_version."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_chunk_repository_shared import (
    _TABLE,
    _rowcount,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_chunk_repository import PostgresChunkRepository


async def _delete_chunks_by_version(
    self: PostgresChunkRepository,
    company_id: CompanyId,
    version_id: str,
    **kwargs: object,
) -> int:
    if self._session is None:
        return self._delete_memory(str(company_id), str(version_id))
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND version_id = :version_id',
        {'company_id': str(company_id), 'version_id': str(version_id)},
    )
    return _rowcount(result, 0)
