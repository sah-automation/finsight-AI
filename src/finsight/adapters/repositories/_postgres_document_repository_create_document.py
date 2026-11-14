"""Auto-extracted helper for PostgresDocumentRepository.create_document."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _document_values,
    _Record,
    _row_to_record,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _create_document(
    self: PostgresDocumentRepository, company_id: CompanyId, **kwargs: object
) -> object:
    values = _document_values(str(company_id), kwargs)
    if self._session is None:
        self._documents.setdefault(str(company_id), {})[values['id']] = _Record(values)
        return _Record(values)
    await self._set_rls_context(company_id)
    columns = list(values)
    sql = (
        f'INSERT INTO {_DOCUMENTS} ({", ".join(columns)}) '
        f'VALUES ({", ".join(":" + column for column in columns)}) RETURNING *'
    )
    result = await self._execute(sql, values)
    return _row_to_record(await self._fetchone(result)) or _Record(values)
