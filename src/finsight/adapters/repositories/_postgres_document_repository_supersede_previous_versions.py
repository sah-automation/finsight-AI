"""Auto-extracted helper for PostgresDocumentRepository.supersede_previous_versions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _VERSIONS,
    _rowcount,
    _text,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, DocumentId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


def _supersede_memory(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object,
    keep: str | None,
) -> int:
    changed = 0
    for record in self._versions.get(str(company_id), {}).values():
        if str(record.get('document_id')) != str(document_id):
            continue
        if record.get('state') != 'committed':
            continue
        if keep is not None and str(record.get('id')) == keep:
            continue
        record['state'] = 'superseded'
        record['updated_at'] = datetime.now(UTC)
        changed += 1
    return changed


async def _supersede_sql(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object,
    keep: str | None,
) -> int:
    sql = (
        f'UPDATE {_VERSIONS} SET state = :superseded, updated_at = now() '
        'WHERE company_id = :company_id AND document_id = :document_id '
        'AND state = :committed'
    )
    params: dict[str, Any] = {
        'company_id': str(company_id),
        'document_id': str(document_id),
        'superseded': 'superseded',
        'committed': 'committed',
    }
    if keep is not None:
        sql += ' AND id <> :keep_version_id'
        params['keep_version_id'] = keep
    result = await self._execute(sql, params)
    return _rowcount(result, 0)


async def _supersede_previous_versions(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object,
    *,
    keep_version_id: object | None = None,
    **kwargs: object,
) -> int:
    keep = _text(keep_version_id)
    if self._session is None:
        return _supersede_memory(self, company_id, document_id, keep)
    await self._set_rls_context(company_id)
    return await _supersede_sql(self, company_id, document_id, keep)
