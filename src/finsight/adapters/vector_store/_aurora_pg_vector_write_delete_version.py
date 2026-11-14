"""Auto-extracted helper for AuroraPgVectorWrite.delete_version."""

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
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


async def _delete_version(
    self: AuroraPgVectorWrite,
    company_id: CompanyId,
    version_id: str,
    **kwargs: object,
) -> int:
    company = _text(company_id)
    version = _text(version_id)
    if self._session is None:
        records = self._memory.get(company, {})
        doomed = [
            chunk_id for chunk_id, record in records.items() if record.get('version_id') == version
        ]
        for chunk_id in doomed:
            del records[chunk_id]
        return len(doomed)
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND version_id = :version_id',
        {'company_id': company, 'version_id': version},
    )
    return _rowcount(result)
