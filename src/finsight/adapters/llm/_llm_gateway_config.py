# ruff: noqa: ANN401
"""LLM gateway configuration helpers."""

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
    return kwargs.get('llm_config') or kwargs.get('model_config')


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _as_model_dict(model: Any) -> dict[str, Any]:
    if isinstance(model, dict):
        return dict(model)
    if isinstance(model, str):
        return {'model_id': model}
    result: dict[str, Any] = {}
    for attr in (
        'model_id',
        'id',
        'name',
        'model',
        'provider',
        'max_tokens',
        'temperature',
        'timeout_seconds',
        'max_retries',
        'retry_base_delay_seconds',
    ):
        if hasattr(model, attr):
            value = getattr(model, attr)
            if value is not None:
                result[attr] = value
    if not result and model is not None:
        result['model_id'] = str(model)
    return result
