"""Auto-extracted helper for PostgresDocumentTableRepository.get."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from finsight.domain.entities.document_table import DocumentTable

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _get(
    self: PostgresDocumentTableRepository, company_id: object, *args: Any, **kwargs: Any
) -> DocumentTable | None:
    return await self.get_document_table(company_id, *args, **kwargs)
