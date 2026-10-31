"""Auto-extracted helper for PostgresDocumentTableRepository.upsert_document_tables."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_table_repository_shared import (
    _is_table,
)

if TYPE_CHECKING:
    import builtins

    from finsight.domain.entities.document_table import DocumentTable


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _upsert_document_tables(
    self: PostgresDocumentTableRepository, company_id: object, *args: Any, **kwargs: Any
) -> builtins.list[DocumentTable]:
    company_id = kwargs.pop('company_id', company_id)
    values = list(args)
    table_value = None
    if company_id is None and values:
        if _is_table(values[0]) and len(values) == 1:
            table_value = values.pop(0)
            company_id = getattr(table_value, 'company_id', None)
        elif not isinstance(values[0], (list, tuple, set)):
            company_id = values.pop(0)
    if values:
        table_value = values.pop(0) if table_value is None else table_value
    if isinstance(table_value, (list, tuple, set)):
        return await self._upsert_many(company_id, table_value, **kwargs)
    if table_value is not None:
        return await self._upsert_many(company_id, [table_value], **kwargs)
    return await self._upsert_many(company_id, kwargs.pop('tables', None), **kwargs)
