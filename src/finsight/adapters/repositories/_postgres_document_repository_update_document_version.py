"""Auto-extracted helper for PostgresDocumentRepository.update_document_version."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _VERSION_UPDATE_FIELDS,
    _VERSIONS,
    _row_to_version,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.document_version import DocumentVersion


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _update_document_version(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    version_id: object,
    **kwargs: object,
) -> DocumentVersion | None:
    values = {k: v for k, v in kwargs.items() if k in _VERSION_UPDATE_FIELDS}
    if self._session is None:
        record = self._versions.get(str(company_id), {}).get(str(version_id))
        if record is None:
            return None
        record.update(values)
        record['updated_at'] = datetime.now(UTC)
        return _row_to_version(record)
    await self._set_rls_context(company_id)
    assignments = [f'{column} = :{column}' for column in values]
    assignments.append('updated_at = now()')
    params: dict[str, Any] = {'company_id': str(company_id), 'id': str(version_id)}
    params.update(values)
    result = await self._execute(
        f'UPDATE {_VERSIONS} SET {", ".join(assignments)} '
        'WHERE company_id = :company_id AND id = :id RETURNING *',
        params,
    )
    return _row_to_version(await self._fetchone(result))
