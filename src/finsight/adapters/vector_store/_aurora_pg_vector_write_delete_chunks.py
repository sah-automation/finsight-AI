"""Auto-extracted helper for AuroraPgVectorWrite.delete_chunks."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from .aurora_pg_vector_write import (
    _TABLE,
    _rowcount,
    _text,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.core.types import ChunkId, CompanyId


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


async def _delete_chunks(
    self: AuroraPgVectorWrite,
    company_id: CompanyId,
    chunk_ids: Sequence[ChunkId],
    **kwargs: object,
) -> int:
    company = _text(company_id)
    ids = [_text(chunk_id) for chunk_id in chunk_ids]
    if not ids:
        return 0
    if self._session is None:
        records = self._memory.get(company, {})
        doomed = [chunk_id for chunk_id in ids if chunk_id in records]
        for chunk_id in doomed:
            del records[chunk_id]
        return len(doomed)
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND chunk_id = ANY(:chunk_ids)',
        {'company_id': company, 'chunk_ids': ids},
    )
    return _rowcount(result)
