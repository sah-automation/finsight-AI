"""Auto-extracted helper for AuroraPgVectorSearch._search_memory."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)
from ._aurora_pg_vector_search_shared import (
    _cosine,
    _keyword_score,
)
from .search_result import SearchResult

if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


def _search_memory(
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
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for record in self._chunks.get(company, {}).values():
        if not include_inactive and not record['is_active']:
            continue
        if access_scope is not None and record['category'] not in access_scope:
            continue
        if document_ids and record['document_id'] not in document_ids:
            continue
        if version_ids and record['version_id'] not in version_ids:
            continue
        vector_score = _cosine(embedding, record['vector'])
        keyword_score = _keyword_score(query, record['text'])
        score = vector_weight * vector_score + keyword_weight * keyword_score
        results.append(
            SearchResult(
                chunk_id=record['chunk_id'],
                company_id=company,
                document_id=record['document_id'],
                version_id=record['version_id'],
                text=record['text'],
                content=record['text'],
                context_header=record['context_header'],
                page_number=record['page_number'],
                category=record['category'],
                is_active=record['is_active'],
                metadata=dict(record['metadata']),
                score=score,
                vector_score=vector_score,
                keyword_score=keyword_score,
            )
        )
    results.sort(key=lambda item: (-item.score, item.chunk_id))
    return results[: max(1, top_k)]
