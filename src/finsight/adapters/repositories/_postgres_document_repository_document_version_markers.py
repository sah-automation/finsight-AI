"""Auto-extracted helper for PostgresDocumentRepository.document_version_markers."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _rows_to_records,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _document_version_markers(
    self: PostgresDocumentRepository, company_id: CompanyId, **kwargs: object
) -> dict[str, str]:
    """Return ``document_id -> marker`` for committed, non-deleted documents."""
    if self._session is None:
        markers: dict[str, str] = {}
        for document_id, record in self._documents.get(str(company_id), {}).items():
            if record.get('deleted_at'):
                continue
            markers[document_id] = str(record.get('document_stamp') or '')
        return markers
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'SELECT id, document_stamp FROM {_DOCUMENTS} '
        'WHERE company_id = :company_id AND deleted_at IS NULL',
        {'company_id': str(company_id)},
    )
    markers = {}
    for record in _rows_to_records(await self._fetchall(result)):
        markers[str(record.get('id'))] = str(record.get('document_stamp') or '')
    return markers
