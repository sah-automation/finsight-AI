"""AskQuestionUseCase alias for the ask-question orchestrator."""

from __future__ import annotations

from .ask_question import AskQuestion


class AskQuestionUseCase(AskQuestion):
    """Compatibility alias class for the ask-question orchestrator."""


__all__ = ['AskQuestionUseCase']
