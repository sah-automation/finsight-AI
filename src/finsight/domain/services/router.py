"""Alias module for the deterministic model router (compatibility)."""

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
