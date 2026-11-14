"""Auto-extracted helper for PostgresDocumentRepository.delete_document."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _delete_document(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> bool:
    if kwargs.get('permanent') or kwargs.get('purge'):
        return await self.purge_document(company_id, document_id, **kwargs)
    return await self.soft_delete_document(company_id, document_id, **kwargs)
