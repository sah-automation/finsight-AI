"""Auto-extracted helper for PostgresDocumentTableRepository.save_document_table."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _save_document_table(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> Any:
    return await self.upsert_document_table(company_id, *args, **kwargs)
