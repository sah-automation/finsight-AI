"""Auto-extracted helper for PostgresDocumentRepository._next_version."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_repository_shared import (
    _VERSIONS,
    _row_value,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


if TYPE_CHECKING:
    from .postgres_document_repository import PostgresDocumentRepository


async def _next_version(
    self: PostgresDocumentRepository, company_id: CompanyId, document_id: object
) -> int:
    result = await self._execute(
        f'SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM {_VERSIONS} '
        'WHERE company_id = :company_id AND document_id = :document_id',
        {'company_id': str(company_id), 'document_id': str(document_id)},
    )
    row = await self._fetchone(result)
    value = _row_value(row, 'next_version')
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 1
