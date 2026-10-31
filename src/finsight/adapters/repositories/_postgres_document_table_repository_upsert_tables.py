"""Auto-extracted helper for PostgresDocumentTableRepository.upsert_tables."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _upsert_tables(
    self: PostgresDocumentTableRepository, company_id: object, *args: Any, **kwargs: Any
) -> Any:
    return await self.upsert_document_tables(company_id, *args, **kwargs)
