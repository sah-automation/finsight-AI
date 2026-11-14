"""Auto-extracted helper for PostgresDocumentRepository.get_document."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _Record,
    _row_to_record,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _get_document(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> object:
    include_deleted = bool(kwargs.get('include_deleted'))
    if self._session is None:
        record = self._documents.get(str(company_id), {}).get(str(document_id))
        if record is None or (record.get('deleted_at') and not include_deleted):
            return None
        return _Record(record)
    await self._set_rls_context(company_id)
    sql = f'SELECT * FROM {_DOCUMENTS} WHERE company_id = :company_id AND id = :id'
    if not include_deleted:
        sql += ' AND deleted_at IS NULL'
    result = await self._execute(sql, {'company_id': str(company_id), 'id': str(document_id)})
    return _row_to_record(await self._fetchone(result))
