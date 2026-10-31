"""Auto-extracted helper for PostgresDocumentRepository._create_version_memory."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _Record,
    _row_to_version,
)

if TYPE_CHECKING:
    from finsight.domain.entities.document_version import DocumentVersion


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


def _create_version_memory(
    self: PostgresDocumentRepository, values: dict[str, Any]
) -> DocumentVersion:
    company_id = values['company_id']
    versions = self._versions.setdefault(company_id, {})
    if values['version'] is None:
        values['version'] = 1 + max(
            (
                int(str(record.get('version') or 0))
                for record in versions.values()
                if str(record.get('document_id')) == values['document_id']
            ),
            default=0,
        )
    now = datetime.now(UTC)
    values.setdefault('created_at', now)
    values['updated_at'] = now
    record = _Record(values)
    versions[values['id']] = record
    version = _row_to_version(record)
    if version is None:
        raise RuntimeError('document version insert returned no row')
    return version
