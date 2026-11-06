"""Auto-extracted helper for PostgresDocumentRepository._memory_documents."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _Record,
    _text,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


def _memory_documents(
    self: PostgresDocumentRepository, company_id: CompanyId, kwargs: dict[str, object]
) -> list[_Record]:
    include_deleted = bool(kwargs.get('include_deleted'))
    only_deleted = bool(kwargs.get('only_deleted'))
    category = _text(kwargs.get('category'))
    status = _text(kwargs.get('status'))
    records: list[_Record] = []
    for record in self._documents.get(str(company_id), {}).values():
        deleted = bool(record.get('deleted_at'))
        if deleted and not include_deleted:
            continue
        if only_deleted and not deleted:
            continue
        if category is not None and str(record.get('category')) != category:
            continue
        if status is not None and str(record.get('status')) != status:
            continue
        rec = _Record(record)
        if 'ingestion_state' not in rec:
            versions = [
                v
                for v in self._versions.get(str(company_id), {}).values()
                if str(v.get('document_id')) == str(rec.get('id'))
            ]
            if versions:
                versions.sort(
                    key=lambda v: str(v.get('updated_at') or v.get('created_at') or ''),
                    reverse=True,
                )
                rec['ingestion_state'] = versions[0].get('state')
        records.append(rec)
    records.sort(key=lambda item: str(item.get('created_at') or ''), reverse=True)
    return records
