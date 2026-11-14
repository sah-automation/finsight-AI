"""Auto-extracted helper for PostgresDocumentRepository.restore_document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _deleted,
    _within_retention,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


def _restore_document_memory(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    kwargs: dict[str, object],
    retention_days: object,
) -> bool:
    record = self._documents.get(str(company_id), {}).get(str(document_id))
    if record is None or not record.get('deleted_at'):
        return False
    if not _within_retention(record.get('deleted_at'), retention_days):
        return False
    record.update(
        {
            'deleted_at': None,
            'deleted_by': None,
            'deleted_reason': None,
            'status': kwargs.get('status') or 'committed',
            'updated_at': datetime.now(UTC),
        }
    )
    return True


async def _restore_document_sql(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    kwargs: dict[str, object],
    retention_days: object,
) -> bool:
    sql = (
        f'UPDATE {_DOCUMENTS} SET deleted_at = NULL, deleted_by = NULL, '
        'deleted_reason = NULL, status = :status, updated_at = now() '
        'WHERE company_id = :company_id AND id = :id AND deleted_at IS NOT NULL'
    )
    params: dict[str, Any] = {
        'company_id': str(company_id),
        'id': str(document_id),
        'status': kwargs.get('status') or 'committed',
    }
    if retention_days is not None:
        sql += ' AND deleted_at >= now() - make_interval(days => :retention_days)'
        params['retention_days'] = int(str(retention_days))
    result = await self._execute(sql + ' RETURNING id', params)
    return _deleted(result)


async def _restore_document(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> bool:
    retention_days = kwargs.get('retention_days') or kwargs.get('deleted_retention_days')
    if self._session is None:
        return _restore_document_memory(self, company_id, document_id, kwargs, retention_days)
    await self._set_rls_context(company_id)
    return await _restore_document_sql(self, company_id, document_id, kwargs, retention_days)
