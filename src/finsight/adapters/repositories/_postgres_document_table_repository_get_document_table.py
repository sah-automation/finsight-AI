"""Auto-extracted helper for PostgresDocumentTableRepository.get_document_table."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.domain.entities.document_table import DocumentTable

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _get_document_table(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> DocumentTable | None:
    company_id = kwargs.pop('company_id', company_id)
    values = list(args)
    if company_id is None and values:
        company_id = values.pop(0)
    return await self._get(company_id, *values, **kwargs)
