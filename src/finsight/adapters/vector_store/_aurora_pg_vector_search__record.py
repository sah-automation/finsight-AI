"""Auto-extracted helper for AuroraPgVectorSearch._record."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._aurora_pg_vector_search_shared import (
    _as_list,
    _metadata,
    _row_value,
    _text,
)

if TYPE_CHECKING:
    from .aurora_pg_vector_search import AuroraPgVectorSearch


def _record(
    self: AuroraPgVectorSearch,
    company: str,
    chunk: object,
    index: int,
    vectors: list[Any],
    categories: list[Any],
) -> dict[str, Any] | None:
    chunk_company = _text(_row_value(chunk, 'company_id'))
    if chunk_company and chunk_company != company:
        return None
    if bool(_row_value(chunk, 'is_parent')):
        return None
    chunk_id = _text(_row_value(chunk, 'chunk_id', 'id'))
    if not chunk_id:
        return None
    vector = vectors[index] if index < len(vectors) else None
    category = (
        _text(categories[index])
        if index < len(categories)
        else _text(_row_value(chunk, 'category'))
    )
    return {
        'chunk_id': chunk_id,
        'company_id': company,
        'document_id': _text(_row_value(chunk, 'document_id')),
        'version_id': _text(_row_value(chunk, 'version_id', 'document_version')),
        'text': _text(_row_value(chunk, 'text', 'content', 'chunk_text')),
        'context_header': _text(_row_value(chunk, 'context_header')),
        'page_number': _row_value(chunk, 'page_number', 'page_from'),
        'category': category,
        'is_active': True
        if _row_value(chunk, 'is_active') is None
        else bool(_row_value(chunk, 'is_active')),
        'metadata': _metadata(_row_value(chunk, 'metadata')),
        'vector': [float(value) for value in _as_list(vector)],
    }
