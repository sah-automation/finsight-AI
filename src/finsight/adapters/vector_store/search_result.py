"""Result row returned by the hybrid search adapter."""

from __future__ import annotations

from typing import Any

_ALIASES = {
    'id': 'chunk_id',
    'chunk': 'chunk_id',
    'content': 'text',
    'chunk_text': 'text',
    'fused_score': 'score',
    'relevance_score': 'score',
    'similarity': 'vector_score',
    'page': 'page_number',
    'page_from': 'page_number',
    'document_version': 'version_id',
    'document_version_id': 'version_id',
}


class SearchResult(dict[str, Any]):
    """A mapping that also exposes search fields as attributes."""

    def __init__(self, **values: Any) -> None:
        super().__init__(values)

    def __getattr__(self, name: str) -> Any:
        key = name if name in self else _ALIASES.get(name, name)
        if key in self:
            return self[key]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name if name in self else _ALIASES.get(name, name)] = value

    def to_dict(self) -> dict[str, Any]:
        return dict(self)


__all__ = ['SearchResult']
