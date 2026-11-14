"""Reranker adapter helpers."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any, cast

_LOGGER = logging.getLogger(__name__)
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


def _first(values: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if values.get(name) is not None:
            return values.get(name)
    return default


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    sections = ('switches', 'reranker', 'retrieval', 'search')
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if config.get(name) is not None:
                return config.get(name)
            for section in sections:
                nested = config.get(section)
                if isinstance(nested, dict) and nested.get(name) is not None:
                    return nested.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in sections:
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
        if any(hasattr(arg, attr) for attr in ('reranker', 'retrieval', 'switches', 'app')):
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
        raise ValueError('company_id is required for reranking')
    return value


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _candidate_value(candidate: object, *names: str) -> object:
    if isinstance(candidate, dict):
        for name in names:
            if candidate.get(name) is not None:
                return candidate.get(name)
        return None
    for name in names:
        if hasattr(candidate, name):
            return getattr(candidate, name)
    return None


def _candidate_text(candidate: object) -> str:
    return _text(
        _candidate_value(candidate, 'text', 'content', 'chunk_text', 'document', 'page_content')
    )


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def _local_score(question: str, candidate: object) -> float:
    query_tokens = _tokens(question)
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(_candidate_text(candidate))) / len(query_tokens)


def _attach_score(candidate: object, score: float) -> object:
    if isinstance(candidate, dict):
        candidate['rerank_score'] = score
        candidate['score'] = score
        return candidate
    target = cast('Any', candidate)
    try:
        target.rerank_score = score
        target.score = score
    except (AttributeError, TypeError):
        pass
    return candidate


def _score_items(response: object, size: int) -> list[float]:
    if response is None:
        return [0.0] * size
    if isinstance(response, dict):
        for key in ('results', 'data', 'scores'):
            if key in response:
                return _score_items(response[key], size)
        return [0.0] * size
    for attr in ('results', 'data', 'scores'):
        value = getattr(response, attr, None)
        if value is not None:
            return _score_items(value, size)
    if not isinstance(response, Iterable) or isinstance(response, (str, bytes)):
        return [0.0] * size
    items = list(response)
    scores = [0.0] * size
    for position, item in enumerate(items):
        index = position
        score = item
        if isinstance(item, dict):
            index = int(item.get('index', item.get('document_index', position)) or position)
            score = item.get('relevance_score', item.get('score', item.get('value', 0.0)))
        elif not isinstance(item, (int, float)):
            index = int(getattr(item, 'index', getattr(item, 'document_index', position)))
            score = getattr(
                item, 'relevance_score', getattr(item, 'score', getattr(item, 'value', 0.0))
            )
        if 0 <= index < size:
            scores[index] = _float(score)
    return scores
