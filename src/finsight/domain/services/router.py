"""Alias module for the deterministic model router (compatibility).

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from .model_router import (
    DeterministicRouter,
    ModelRouter,
    ModelSelectionRouter,
    QuestionRouter,
    Router,
    route_question,
)

__all__ = [
    'DeterministicRouter',
    'ModelRouter',
    'ModelSelectionRouter',
    'QuestionRouter',
    'Router',
    'route_question',
]
