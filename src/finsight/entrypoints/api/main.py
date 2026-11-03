"""ASGI entrypoint for the FinSight API (deployment/public surface).

Exposes ``create_app`` and a lazily-built ``app`` for ``uvicorn``. The app is
built on first attribute access so importing this module has no wiring side
effects. Retained because the CDK handler references this module. Owner:
platform; removal condition: none.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from finsight.entrypoints.api.app import create_app

__all__ = ['create_app']


@cache
def _get_app() -> Any:
    """Build the ASGI application once, on first access."""
    return create_app()


def __getattr__(name: str) -> Any:
    """Resolve ``app`` lazily for ``uvicorn`` and ``from ...main import app``."""
    if name != 'app':
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    return _get_app()
