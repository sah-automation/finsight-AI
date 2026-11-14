"""Shared helpers for AuroraPgVectorSearch."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from typing import Any

from .search_result import SearchResult

_TOKEN_RE = re.compile(r'[a-z0-9]+')

_STOPWORDS = frozenset(
    {
        'a',
        'an',
        'and',
        'are',
        'as',
        'at',
        'be',
        'by',
        'for',
        'in',
        'is',
        'of',
        'on',
        'or',
        'the',
        'to',
        'was',
        'were',
    }
)


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if config.get(name) is not None:
                return config.get(name)
            for section in ('retrieval', 'search', 'vector_store'):
                nested = config.get(section)
                if isinstance(nested, dict) and nested.get(name) is not None:
                    return nested.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in ('retrieval', 'search', 'vector_store'):
                nested = getattr(config, section, None)
                value = (
                    nested.get(name) if isinstance(nested, dict) else getattr(nested, name, None)
                )
                if value is not None:
                    return value
    return default


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if any(hasattr(arg, attr) for attr in ('retrieval', 'switches', 'app', 'vector_store')):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        config = getattr(container, 'config', None) if container is not None else None
        if config is not None:
            return config
    return None


def _company(company_id: object) -> str:
    value = _text(company_id).strip()
    if not value:
        raise ValueError('company_id is required for hybrid search')
    return value


def _as_list(value: object) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def _keyword_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(text)) / len(query_tokens)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(float(a) ** 2 for a in left))
    right_norm = math.sqrt(sum(float(b) ** 2 for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _row_value(row: object, *names: str) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for name in names:
            try:
                if name in mapping:
                    return mapping[name]
            except TypeError:
                continue
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _metadata(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _row_to_result(row: object) -> SearchResult:
    text = _text(_row_value(row, 'content', 'text', 'chunk_text'))
    metadata = _metadata(_row_value(row, 'metadata'))
    return SearchResult(
        chunk_id=_text(_row_value(row, 'chunk_id', 'id')),
        company_id=_text(_row_value(row, 'company_id')),
        document_id=_text(_row_value(row, 'document_id')),
        version_id=_text(_row_value(row, 'version_id', 'document_version')),
        text=text,
        content=text,
        context_header=_text(_row_value(row, 'context_header')),
        page_number=_row_value(row, 'page_number', 'page_from'),
        category=_text(_row_value(row, 'category')),
        is_active=bool(_row_value(row, 'is_active')),
        metadata=metadata,
        score=_float(_row_value(row, 'score', 'fused_score')),
        vector_score=_float(_row_value(row, 'vector_score', 'similarity')),
        keyword_score=_float(_row_value(row, 'keyword_score')),
    )
