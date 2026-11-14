"""Auto-extracted helper for AuroraPgVectorSearch._sql."""

from __future__ import annotations

import json
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


def _score_expressions(
    query: str,
    embedding: list[float],
    keyword_weight: float,
    params: dict[str, Any],
) -> tuple[str, str]:
    vector_expr = '0.0'
    if embedding:
        params['embedding'] = json.dumps(embedding)
        vector_expr = '1 - (c.embedding <=> CAST(:embedding AS vector))'
    keyword_expr = '0.0'
    if query and keyword_weight > 0.0:
        params['query'] = query
        keyword_expr = (
            "ts_rank_cd(to_tsvector('english', coalesce(c.content, '')), "
            "plainto_tsquery('english', :query))"
        )
    return vector_expr, keyword_expr


def _search_filters(
    self: AuroraPgVectorSearch,
    include_inactive: bool,
    access_scope: list[str] | None,
    document_ids: list[str],
    version_ids: list[str],
    values: dict[str, Any],
    params: dict[str, Any],
) -> list[str]:
    filters = [
        'c.company_id = :company_id',
        'c.is_parent = FALSE',
        'd.deleted_at IS NULL',
    ]
    if not include_inactive:
        filters.append('c.is_active = TRUE')
    filters.extend(self._filter_sql(access_scope, document_ids, version_ids, values, params))
    return filters


def _sql(
    self: AuroraPgVectorSearch,
    query: str,
    embedding: list[float],
    access_scope: list[str] | None,
    document_ids: list[str],
    version_ids: list[str],
    vector_weight: float,
    keyword_weight: float,
    include_inactive: bool,
    values: dict[str, Any],
    params: dict[str, Any],
) -> str:
    vector_expr, keyword_expr = _score_expressions(query, embedding, keyword_weight, params)
    score_expr = f'({vector_weight} * ({vector_expr}) + {keyword_weight} * ({keyword_expr}))'
    filters = _search_filters(
        self, include_inactive, access_scope, document_ids, version_ids, values, params
    )
    return (
        'SELECT c.chunk_id, c.company_id, c.document_id, c.version_id, c.content, '
        'c.context_header, c.page_number, c.metadata, c.is_active, d.category, '
        f'{vector_expr} AS vector_score, {keyword_expr} AS keyword_score, '
        f'{score_expr} AS score '
        'FROM document_chunks c '
        'JOIN documents d ON d.company_id = c.company_id AND d.id = c.document_id '
        f'WHERE {" AND ".join(filters)} '
        'ORDER BY score DESC, c.chunk_id ASC LIMIT :top_k'
    )
