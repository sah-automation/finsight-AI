"""Auto-extracted helper for PostgresDocumentTableRepository.upsert_document_table."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_table_repository_shared import (
    _is_table,
    _to_table,
)

if TYPE_CHECKING:
    from finsight.domain.entities.document_table import DocumentTable


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _upsert_document_table(
    self: PostgresDocumentTableRepository, company_id: object, *args: Any, **kwargs: Any
) -> DocumentTable:
    company_id = kwargs.pop('company_id', company_id)
    values = list(args)
    table_value = None
    if company_id is None and values:
        if _is_table(values[0]):
            table_value = values.pop(0)
            company_id = getattr(table_value, 'company_id', None)
        else:
            company_id = values.pop(0)
    if values:
        table_value = values.pop(0) if table_value is None else table_value
    if isinstance(table_value, (list, tuple, set)):
        saved = await self._upsert_many(company_id, table_value, **kwargs)
        return saved[0] if saved else _to_table(company_id, None, **kwargs)
    saved = await self._upsert_many(
        company_id, table_value if table_value is not None else None, **kwargs
    )
    if not saved and (table_value is None and kwargs):
        saved = await self._upsert_many(company_id, None, **kwargs)
    if not saved:
        return _to_table(company_id, None, **(kwargs or {}))
    return saved[0]
