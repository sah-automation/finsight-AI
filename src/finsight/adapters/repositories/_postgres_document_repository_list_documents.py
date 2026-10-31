"""Auto-extracted helper for PostgresDocumentRepository.list_documents."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _document_filters,
    _order_and_page,
    _rows_to_records,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _list_documents(
    self: PostgresDocumentRepository, company_id: CompanyId, **kwargs: object
) -> list[object]:
    if self._session is None:
        return list(self._memory_documents(company_id, kwargs))
    await self._set_rls_context(company_id)
    where, params = _document_filters(str(company_id), kwargs)
    sql = f'SELECT * FROM {_DOCUMENTS} WHERE {" AND ".join(where)}'
    sql += _order_and_page(kwargs)
    result = await self._execute(sql, params)
    return list(_rows_to_records(await self._fetchall(result)))
