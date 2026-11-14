"""Auto-extracted helper for PostgresDocumentRepository.purge_document."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _DOCUMENTS,
    _deleted,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _purge_document(
    self: PostgresDocumentRepository,
    company_id: CompanyId,
    document_id: object,
    **kwargs: object,
) -> bool:
    if self._session is None:
        documents = self._documents.get(str(company_id), {})
        if str(document_id) not in documents:
            return False
        del documents[str(document_id)]
        versions = self._versions.get(str(company_id), {})
        for version_id in [
            key
            for key, record in versions.items()
            if str(record.get('document_id')) == str(document_id)
        ]:
            del versions[version_id]
        return True
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'DELETE FROM {_DOCUMENTS} WHERE company_id = :company_id AND id = :id RETURNING id',
        {'company_id': str(company_id), 'id': str(document_id)},
    )
    return _deleted(result)
