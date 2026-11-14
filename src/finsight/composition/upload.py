"""Composition helpers for the upload entrypoint."""

from __future__ import annotations

from typing import Any

from .container import (
    build_upload_use_case as _build_upload_use_case,
)
from .container import (
    get_upload_use_case as _get_upload_use_case,
)


def build_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    return _build_upload_use_case(*args, **kwargs)


def get_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    return _get_upload_use_case(*args, **kwargs)


def create_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    return build_upload_use_case(*args, **kwargs)


def build_container(*args: Any, **kwargs: Any) -> Any:
    from .container import build_container as _build_container

    return _build_container(*args, **kwargs)
