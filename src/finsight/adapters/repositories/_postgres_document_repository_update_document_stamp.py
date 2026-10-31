"""Auto-extracted helper for PostgresDocumentRepository.update_document_stamp."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _update_document_stamp(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    stamp: object,
    **kwargs: object,
) -> object:
    value = getattr(stamp, 'value', stamp)
    return await self.update_document(company_id, document_id, document_stamp=str(value), **kwargs)
