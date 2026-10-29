"""Alias module for the deterministic model router (compatibility)."""

from .model_router import (
    DeterministicRouter,
    ModelRouter,
    ModelSelectionRouter,
    QuestionRouter,
    Router,
    route_question,
)
from .route_decision import RouteDecision

__all__ = [
    "DeterministicRouter",
    "ModelRouter",
    "ModelSelectionRouter",
    "QuestionRouter",
    "Router",
    "route_question",
]
