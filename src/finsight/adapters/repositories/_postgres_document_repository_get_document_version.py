"""Auto-extracted helper for PostgresDocumentRepository.get_document_version."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _VERSIONS,
    _row_to_version,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.document_version import DocumentVersion


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _get_document_version(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    version_id: object,
    **kwargs: object,
) -> DocumentVersion | None:
    include_deleted = bool(kwargs.get('include_deleted'))
    if self._session is None:
        record = self._versions.get(str(company_id), {}).get(str(version_id))
        if record is None or record.get('deleted_at'):
            return None
        return _row_to_version(record)
    await self._set_rls_context(company_id)
    sql = f'SELECT v.* FROM {_VERSIONS} v WHERE v.company_id = :company_id AND v.id = :id'
    if not include_deleted:
        sql += (
            f' AND EXISTS (SELECT 1 FROM {_DOCUMENTS} d WHERE d.id = v.document_id '
            'AND d.company_id = v.company_id AND d.deleted_at IS NULL)'
        )
    result = await self._execute(sql, {'company_id': str(company_id), 'id': str(version_id)})
    return _row_to_version(await self._fetchone(result))
