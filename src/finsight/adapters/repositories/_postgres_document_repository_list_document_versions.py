"""Auto-extracted helper for PostgresDocumentRepository.list_document_versions."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _VERSIONS,
    _rows_to_versions,
    _version_filters,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, DocumentId
    from finsight.domain.entities.document_version import DocumentVersion


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _list_document_versions(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object | None = None,
    **kwargs: object,
) -> list[DocumentVersion]:
    if self._session is None:
        return self._list_versions_memory(company_id, document_id, kwargs)
    await self._set_rls_context(company_id)
    where, params = _version_filters(str(company_id), document_id, kwargs)
    sql = f'SELECT v.* FROM {_VERSIONS} v WHERE {" AND ".join(where)} ORDER BY v.version DESC'
    result = await self._execute(sql, params)
    return _rows_to_versions(await self._fetchall(result))
