"""Auto-extracted helper for PostgresDocumentRepository.list_versions_for_audit."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, DocumentId
    from finsight.domain.entities.document_version import DocumentVersion

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _list_versions_for_audit(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object | None = None,
    **kwargs: object,
) -> list[DocumentVersion]:
    filters = dict(kwargs)
    filters.setdefault('include_deleted', True)
    filters.setdefault('include_superseded', True)
    return await self.list_document_versions(company_id, document_id, **filters)
