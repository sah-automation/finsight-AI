"""Auto-extracted helper for AuroraPgVectorSearch._search_sql."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._aurora_pg_vector_search_shared import (
    _row_to_result,
)

if TYPE_CHECKING:
    from .search_result import SearchResult


if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


async def _search_sql(
    self: AuroraPgVectorSearch,
    company: str,
    query: str,
    embedding: list[float],
    access_scope: list[str] | None,
    document_ids: list[str],
    version_ids: list[str],
    top_k: int,
    vector_weight: float,
    keyword_weight: float,
    include_inactive: bool,
    values: dict[str, Any],
) -> list[SearchResult]:
    await self._execute(
        "SELECT set_config('app.company_id', :company_id, true)", {'company_id': company}
    )
    params: dict[str, Any] = {'company_id': company, 'top_k': max(1, top_k)}
    sql = self._sql(
        query,
        embedding,
        access_scope,
        document_ids,
        version_ids,
        vector_weight,
        keyword_weight,
        include_inactive,
        values,
        params,
    )
    result = await self._execute(sql, params)
    return [_row_to_result(row) for row in await self._fetchall(result)]
