"""Composition helpers for the reprocess use case."""

from __future__ import annotations

from typing import Any

from .container import (
    build_reprocess_use_case as _build_reprocess_use_case,
)
from .container import (
    get_default_container,
)
from .container import (
    get_default_reprocess_use_case as _get_default_reprocess_use_case,
)


def _container(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        from .container import build_container as _build_container

        return _build_container(*args, **kwargs)
    return get_default_container()


def build_reprocess_use_case(*args: Any, **kwargs: Any) -> Any:
    provided = kwargs.get('reprocess_use_case') or kwargs.get('use_case')
    if provided is not None:
        return provided
    container = _container(*args, **kwargs)
    if container is not None:
        for attr in ('reprocess_use_case', 'reprocess'):
            value = getattr(container, attr, None)
            if value is not None:
                return value
    return _build_reprocess_use_case(*args, **kwargs)


def get_reprocess_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_reprocess_use_case(*args, **kwargs)
    default = _get_default_reprocess_use_case()
    if default is not None:
        return default
    container = get_default_container()
    if container is not None:
        for attr in ('reprocess_use_case', 'reprocess'):
            value = getattr(container, attr, None)
            if value is not None:
                return value
    return build_reprocess_use_case()


def create_reprocess_use_case(*args: Any, **kwargs: Any) -> Any:
    return build_reprocess_use_case(*args, **kwargs)


__all__ = [
    'build_reprocess_use_case',
    'create_reprocess_use_case',
    'get_reprocess_use_case',
]
