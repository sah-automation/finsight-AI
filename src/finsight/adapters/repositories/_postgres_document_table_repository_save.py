"""Auto-extracted helper for PostgresDocumentTableRepository.save."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _save(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> Any:
    return await self.upsert(company_id, *args, **kwargs)
