"""Auto-extracted helper for AuroraPgVectorSearch.clear."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)
from ._aurora_pg_vector_search_shared import (
    _company,
)

if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


async def _clear(self: AuroraPgVectorSearch, company_id: object) -> None:
    self._chunks.pop(_company(company_id), None)
