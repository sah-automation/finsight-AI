"""Auto-extracted helper for PostgresDocumentRepository._list_versions_memory."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _row_to_version,
    _text,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, DocumentId
    from finsight.domain.entities.document_version import DocumentVersion


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


def _list_versions_memory(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: DocumentId | object | None,
    kwargs: dict[str, object],
) -> list[DocumentVersion]:
    state = _text(kwargs.get('state'))
    include_superseded = bool(kwargs.get('include_superseded', True))
    include_deleted = bool(kwargs.get('include_deleted'))
    documents = self._documents.get(str(company_id), {})
    versions: list[DocumentVersion] = []
    for record in self._versions.get(str(company_id), {}).values():
        if document_id is not None and str(record.get('document_id')) != str(document_id):
            continue
        if not include_deleted:
            parent = documents.get(str(record.get('document_id')))
            if parent is not None and parent.get('deleted_at'):
                continue
        if state is not None and str(record.get('state')) != state:
            continue
        if not include_superseded and record.get('state') == 'superseded':
            continue
        version = _row_to_version(record)
        if version is not None:
            versions.append(version)
    versions.sort(key=lambda item: int(str(item.version or 0)), reverse=True)
    return versions
