"""Auto-extracted helper for PostgresDocumentTableRepository.get_document_tables."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    import builtins

    from finsight.domain.entities.document_table import DocumentTable

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _get_document_tables(
    self: PostgresDocumentTableRepository, company_id: object, *args: Any, **kwargs: Any
) -> builtins.list[DocumentTable]:
    return await self.list_document_tables(company_id, *args, **kwargs)
