"""Auto-extracted helper for AuroraPgVectorWrite.commit_version."""

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

_COMMIT_VERSION_SQL = (
    f'WITH target AS ('
    f'SELECT DISTINCT document_id FROM {_TABLE} '
    'WHERE company_id = :company_id AND version_id = :version_id), '
    f'deactivated AS ('
    f'UPDATE {_TABLE} SET is_active = FALSE, updated_at = now() '
    'WHERE company_id = :company_id AND is_active = TRUE '
    'AND document_id IN (SELECT document_id FROM target) '
    'AND version_id <> :version_id RETURNING 1) '
    f'UPDATE {_TABLE} SET is_active = TRUE, updated_at = now() '
    'WHERE company_id = :company_id AND version_id = :version_id '
    'AND embedding IS NOT NULL'
)


def _commit_version_memory(
    self: AuroraPgVectorWrite,
    company: str,
    version: str,
) -> int:
    records = self._memory.get(company, {})
    documents = {
        record.get('document_id')
        for record in records.values()
        if record.get('version_id') == version
    }
    for record in records.values():
        if record.get('document_id') not in documents:
            continue
        if record.get('version_id') != version and record.get('is_active'):
            record['is_active'] = False
    activated = 0
    for record in records.values():
        if record.get('version_id') != version or record.get('embedding') is None:
            continue
        if not record.get('is_active'):
            activated += 1
        record['is_active'] = True
    return activated


async def _commit_version(
    self: AuroraPgVectorWrite,
    company_id: CompanyId,
    version_id: str,
    **kwargs: object,
) -> int:
    company = _text(company_id)
    version = _text(version_id)
    if self._session is None:
        return _commit_version_memory(self, company, version)
    await self._set_rls_context(company_id)
    result = await self._execute(
        _COMMIT_VERSION_SQL, {'company_id': company, 'version_id': version}
    )
    return _rowcount(result)
