"""Auto-extracted helper for AuroraPgVectorSearch.search."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._aurora_pg_vector_search_shared import (
    _as_list,
    _company,
    _first,
    _float,
    _text,
)

if TYPE_CHECKING:
    from .search_result import SearchResult


if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


def _search_options(
    self: AuroraPgVectorSearch,
    values: dict[str, Any],
) -> tuple[list[str] | None, list[str], list[str], int, float, float, bool]:
    access_scope = self._scope(values)
    document_ids = [_text(item) for item in _as_list(_first(values, 'document_ids', 'documents'))]
    version_ids = [_text(item) for item in _as_list(_first(values, 'version_ids', 'versions'))]
    top_k = int(_first(values, 'top_k', 'limit', default=self.top_k) or self.top_k)
    vector_weight = _float(_first(values, 'vector_weight', default=self.vector_weight))
    keyword_weight = _float(_first(values, 'keyword_weight', default=self.keyword_weight))
    include_inactive = bool(_first(values, 'include_inactive', default=False))
    hybrid = bool(_first(values, 'hybrid_search_enabled', default=self.hybrid_search_enabled))
    if not hybrid:
        keyword_weight = 0.0
    return (
        access_scope,
        document_ids,
        version_ids,
        top_k,
        vector_weight,
        keyword_weight,
        include_inactive,
    )


async def _search(
    self: AuroraPgVectorSearch, company_id: object, *args: Any, **kwargs: Any
) -> list[SearchResult]:
    company = _company(company_id)
    values: dict[str, Any] = dict(kwargs)
    query, embedding = self._parse_args(args, values)
    options = _search_options(self, values)
    if self._session is None:
        return self._search_memory(company, query, embedding, *options)
    return await self._search_sql(company, query, embedding, *options, values)
