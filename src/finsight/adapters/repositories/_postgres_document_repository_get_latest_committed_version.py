"""Auto-extracted helper for PostgresDocumentRepository.get_latest_committed_version."""

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


async def _get_latest_committed_version(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object,
    **kwargs: object,
) -> DocumentVersion | None:
    versions = await self.list_document_versions(company_id, document_id, state='committed')
    return versions[0] if versions else None
