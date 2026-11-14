"""Auto-extracted helper for PostgresDocumentRepository.create_document_version."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _VERSIONS,
    _row_to_version,
    _version_values,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.document_version import DocumentVersion


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _create_document_version(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    *,
    document_version: DocumentVersion | None = None,
    **kwargs: object,
) -> DocumentVersion:
    values = _version_values(str(company_id), document_version, dict(kwargs))
    if not values['document_id']:
        raise ValueError('document_id is required to create a document version')
    if self._session is None:
        return self._create_version_memory(values)
    await self._set_rls_context(company_id)
    if values['version'] is None:
        values['version'] = await self._next_version(company_id, values['document_id'])
    columns = list(values)
    sql = (
        f'INSERT INTO {_VERSIONS} ({", ".join(columns)}) '
        f'VALUES ({", ".join(":" + column for column in columns)}) RETURNING *'
    )
    result = await self._execute(sql, values)
    version = _row_to_version(await self._fetchone(result))
    if version is None:
        raise RuntimeError('document version insert returned no row')
    return version
