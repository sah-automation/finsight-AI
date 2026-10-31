"""Auto-extracted helper for PostgresDocumentTableRepository.upsert."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _upsert(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> Any:
    if kwargs.get('tables') is not None or any(isinstance(v, (list, tuple, set)) for v in args):
        return await self.upsert_document_tables(company_id, *args, **kwargs)
    return await self.upsert_document_table(company_id, *args, **kwargs)
