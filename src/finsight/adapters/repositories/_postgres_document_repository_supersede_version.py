"""Auto-extracted helper for PostgresDocumentRepository.supersede_version."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.document_version import DocumentVersion

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _supersede_version(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    version_id: object,
    **kwargs: object,
) -> DocumentVersion | None:
    return await self.update_document_version(company_id, version_id, state='superseded', **kwargs)
