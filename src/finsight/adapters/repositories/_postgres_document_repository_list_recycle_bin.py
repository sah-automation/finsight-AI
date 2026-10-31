"""Auto-extracted helper for PostgresDocumentRepository.list_recycle_bin."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _list_recycle_bin(
    self: PostgresDocumentRepository, company_id: CompanyId, **kwargs: object
) -> list[object]:
    filters = dict(kwargs)
    filters['only_deleted'] = True
    filters['include_deleted'] = True
    return await self.list_documents(company_id, **filters)
