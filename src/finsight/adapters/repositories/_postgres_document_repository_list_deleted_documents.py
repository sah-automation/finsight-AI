"""Auto-extracted helper for PostgresDocumentRepository.list_deleted_documents."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _list_deleted_documents(
    self: PostgresDocumentRepository, company_id: CompanyId, **kwargs: object
) -> list[object]:
    return await self.list_recycle_bin(company_id, **kwargs)
