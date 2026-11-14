"""Auto-extracted helper for PostgresDocumentRepository.purge_expired_documents."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _rowcount,
    _within_retention,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _purge_expired_documents(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    retention_days: int,
    **kwargs: object,
) -> int:
    cutoff = int(retention_days)
    if self._session is None:
        documents = self._documents.get(str(company_id), {})
        doomed = [
            document_id
            for document_id, record in documents.items()
            if record.get('deleted_at') and not _within_retention(record.get('deleted_at'), cutoff)
        ]
        for document_id in doomed:
            await self.purge_document(company_id, document_id)
        return len(doomed)
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'DELETE FROM {_DOCUMENTS} WHERE company_id = :company_id '
        'AND deleted_at IS NOT NULL AND deleted_at < now() - make_interval(days => :days)',
        {'company_id': str(company_id), 'days': cutoff},
    )
    return _rowcount(result, 0)
