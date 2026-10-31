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


def _record_key(chunk: object, company: str) -> str | None:
    chunk_company = _text(_row_value(chunk, 'company_id'))
    if chunk_company and chunk_company != company:
        return None
    if bool(_row_value(chunk, 'is_parent')):
        return None
    return _text(_row_value(chunk, 'chunk_id', 'id')) or None


def _record_vector(
    vectors: list[Any],
    categories: list[Any],
    chunk: object,
    index: int,
) -> tuple[list[float], str]:
    vector = vectors[index] if index < len(vectors) else None
    category = (
        _text(categories[index])
        if index < len(categories)
        else _text(_row_value(chunk, 'category'))
    )
    return [float(value) for value in _as_list(vector)], category


def _record(
    self: AuroraPgVectorSearch,
    company: str,
    chunk: object,
    index: int,
    vectors: list[Any],
    categories: list[Any],
) -> dict[str, Any] | None:
    chunk_id = _record_key(chunk, company)
    if chunk_id is None:
        return None
    vector, category = _record_vector(vectors, categories, chunk, index)
    is_active = _row_value(chunk, 'is_active')
    return {
        'chunk_id': chunk_id,
        'company_id': company,
        'document_id': _text(_row_value(chunk, 'document_id')),
        'version_id': _text(_row_value(chunk, 'version_id', 'document_version')),
        'text': _text(_row_value(chunk, 'text', 'content', 'chunk_text')),
        'context_header': _text(_row_value(chunk, 'context_header')),
        'page_number': _row_value(chunk, 'page_number', 'page_from'),
        'category': category,
        'is_active': True if is_active is None else bool(is_active),
        'metadata': _metadata(_row_value(chunk, 'metadata')),
        'vector': vector,
    }
