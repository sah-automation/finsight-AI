# ruff: noqa: PLR0911, PLR0912
"""Embedding adapter helpers."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'switches') or hasattr(arg, 'llm') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return kwargs.get('embedding_config') or kwargs.get('model_config')


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _as_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, dict):
        for key in ('texts', 'inputs', 'input', 'data', 'values'):
            if value.get(key) is not None:
                return _as_texts(value.get(key))
        return [str(value)]
    return [str(value)]


def _extract_vectors(result: Any) -> list[list[float]]:
    if result is None:
        return []
    if isinstance(result, dict):
        for key in ('data', 'embeddings', 'results'):
            value = result.get(key)
            if value is not None:
                return _extract_vectors(value)
        if 'embedding' in result:
            return [list(result['embedding'])]
    if isinstance(result, (list, tuple)):
        if not result:
            return []
        if isinstance(result[0], (int, float)):
            return [list(result)]
        vectors: list[list[float]] = []
        for item in result:
            if isinstance(item, (list, tuple)):
                vectors.append([float(x) for x in item])
            elif isinstance(item, dict):
                emb = item.get('embedding', item.get('vector', item.get('values')))
                if emb is not None:
                    vectors.append([float(x) for x in emb])
            elif hasattr(item, 'embedding'):
                vectors.append([float(x) for x in item.embedding])
            else:
                vectors.append([float(x) for x in item])
        return vectors
    for attr in ('data', 'embeddings', 'results'):
        value = getattr(result, attr, None)
        if value is not None:
            return _extract_vectors(value)
    value = getattr(result, 'embedding', None)
    if value is not None:
        return _extract_vectors(value)
    raise TypeError('Unable to extract embeddings from result')
