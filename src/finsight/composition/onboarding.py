"""Composition helpers for the onboarding use case."""

from __future__ import annotations

from typing import Any

from .container import (
    build_onboarding_use_case as _build_onboarding_use_case,
)
from .container import (
    get_onboarding_use_case as _get_onboarding_use_case,
)


def build_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    """Build an onboarding use case instance."""
    return _build_onboarding_use_case(*args, **kwargs)


def get_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    """Return an onboarding use case instance."""
    return _get_onboarding_use_case(*args, **kwargs)


def create_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    """Alias for build_onboarding_use_case."""
    return build_onboarding_use_case(*args, **kwargs)


def build_container(*args: Any, **kwargs: Any) -> Any:
    from .container import build_container as _build_container

    return _build_container(*args, **kwargs)
