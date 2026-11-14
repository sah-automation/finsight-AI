"""Auto-extracted helper for AuroraPgVectorWrite.mark_version_inactive."""

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

_MARK_VERSION_INACTIVE_SQL = (
    f'UPDATE {_TABLE} SET is_active = FALSE, updated_at = now() '
    'WHERE company_id = :company_id AND version_id = :version_id AND is_active = TRUE '
    'AND (cardinality(:exclude_ids) = 0 OR NOT (chunk_id = ANY(:exclude_ids)))'
)


def _mark_version_inactive_memory(
    self: AuroraPgVectorWrite,
    company: str,
    version: str,
    excluded: set[str],
) -> int:
    records = self._memory.get(company, {})
    changed = 0
    for chunk_id, record in records.items():
        if record.get('version_id') != version or chunk_id in excluded:
            continue
        if record.get('is_active'):
            record['is_active'] = False
            changed += 1
    return changed


async def _mark_version_inactive(
    self: AuroraPgVectorWrite,
    company_id: CompanyId,
    version_id: str,
    *,
    exclude_chunk_ids: Sequence[ChunkId] = (),
    **kwargs: object,
) -> int:
    company = _text(company_id)
    version = _text(version_id)
    excluded = {_text(chunk_id) for chunk_id in exclude_chunk_ids}
    if self._session is None:
        return _mark_version_inactive_memory(self, company, version, excluded)
    await self._set_rls_context(company_id)
    result = await self._execute(
        _MARK_VERSION_INACTIVE_SQL,
        {
            'company_id': company,
            'version_id': version,
            'exclude_ids': list(excluded),
        },
    )
    return _rowcount(result)
