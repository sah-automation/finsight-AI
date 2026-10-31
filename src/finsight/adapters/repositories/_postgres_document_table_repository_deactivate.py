"""Auto-extracted helper for PostgresDocumentTableRepository.deactivate."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _deactivate(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> int:
    return await self._mark_inactive(company_id, *args, **kwargs)
