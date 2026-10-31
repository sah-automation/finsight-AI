"""Auto-extracted helper for PostgresDocumentRepository.soft_delete_document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _deleted,
    _text,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _soft_delete_document(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> bool:
    deleted_at = datetime.now(UTC)
    deleted_by = _text(kwargs.get('deleted_by') or kwargs.get('user_id'))
    reason = _text(kwargs.get('reason') or kwargs.get('deleted_reason'))
    if self._session is None:
        record = self._documents.get(str(company_id), {}).get(str(document_id))
        if record is None or record.get('deleted_at'):
            return False
        record.update(
            {
                'deleted_at': deleted_at,
                'deleted_by': deleted_by,
                'deleted_reason': reason,
                'status': 'deleted',
                'updated_at': deleted_at,
            }
        )
        return True
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'UPDATE {_DOCUMENTS} SET deleted_at = now(), deleted_by = :deleted_by, '
        'deleted_reason = :reason, status = :status, updated_at = now() '
        'WHERE company_id = :company_id AND id = :id AND deleted_at IS NULL RETURNING id',
        {
            'company_id': str(company_id),
            'id': str(document_id),
            'deleted_by': deleted_by,
            'reason': reason,
            'status': 'deleted',
        },
    )
    return _deleted(result)
