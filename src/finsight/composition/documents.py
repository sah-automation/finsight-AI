"""Composition helpers for the document library entrypoint (Slice 4.5)."""

from __future__ import annotations

from typing import Any

from .container import (
    build_container as _build_container,
)
from .container import (
    build_document_repository as _build_document_repository,
)
from .container import (
    get_default_container,
)


def _container(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return _build_container(*args, **kwargs)
    return get_default_container()


def build_document_repository(*args: Any, **kwargs: Any) -> Any:
    return _build_document_repository(*args, **kwargs)


def build_document_use_case(*args: Any, **kwargs: Any) -> Any:
    provided = kwargs.get('document_use_case') or kwargs.get('use_case') or kwargs.get('repository')
    if provided is not None:
        return provided
    container = _container(*args, **kwargs)
    if container is not None and getattr(container, 'document_repository', None) is not None:
        return container.document_repository
    return _build_document_repository(*args, **kwargs)


def get_document_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_document_use_case(*args, **kwargs)
    container = get_default_container()
    if container is not None and getattr(container, 'document_repository', None) is not None:
        return container.document_repository
    return build_document_use_case()


def create_document_use_case(*args: Any, **kwargs: Any) -> Any:
    return build_document_use_case(*args, **kwargs)


def get_document_repository(*args: Any, **kwargs: Any) -> Any:
    return build_document_repository(*args, **kwargs)


def build_container(*args: Any, **kwargs: Any) -> Any:
    from .container import build_container as _bc

    return _bc(*args, **kwargs)


def get_container(*args: Any, **kwargs: Any) -> Any:
    from .container import get_container as _gc

    return _gc(*args, **kwargs)
