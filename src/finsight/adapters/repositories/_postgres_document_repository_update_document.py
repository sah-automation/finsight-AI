"""Auto-extracted helper for PostgresDocumentRepository.update_document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENT_UPDATE_FIELDS,
    _DOCUMENTS,
    _Record,
    _row_to_record,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _update_document(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> object:
    values = {k: v for k, v in kwargs.items() if k in _DOCUMENT_UPDATE_FIELDS}
    if self._session is None:
        record = self._documents.get(str(company_id), {}).get(str(document_id))
        if record is None:
            return None
        record.update(values)
        record['updated_at'] = datetime.now(UTC)
        return _Record(record)
    await self._set_rls_context(company_id)
    assignments = [f'{column} = :{column}' for column in values]
    assignments.append('updated_at = now()')
    params: dict[str, Any] = {'company_id': str(company_id), 'id': str(document_id)}
    params.update(values)
    sql = (
        f'UPDATE {_DOCUMENTS} SET {", ".join(assignments)} '
        'WHERE company_id = :company_id AND id = :id RETURNING *'
    )
    result = await self._execute(sql, params)
    return _row_to_record(await self._fetchone(result))
