"""Auto-extracted helper for PostgresDocumentRepository.get_document_stamp."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _get_document_stamp(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> object:
    document = await self.get_document(company_id, document_id, **kwargs)
    if document is None:
        return None
    if isinstance(document, dict):
        return document.get('document_stamp')
    return getattr(document, 'document_stamp', None)
