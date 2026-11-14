"""Step result discriminator for the source-viewer pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .source_viewer_context import SourceViewerContext  # noqa: TC001


@dataclass(frozen=True)
class StepResult:
    """Outcome of a single source-viewer step."""

    context: SourceViewerContext
    kind: Literal['continue', 'not_available', 'error'] = 'continue'
    error: Exception | None = None

    @classmethod
    def continue_(cls, context: SourceViewerContext) -> StepResult:
        return cls(context=context, kind='continue')

    @classmethod
    def stop_with_not_available(cls, context: SourceViewerContext) -> StepResult:
        return cls(context=context, kind='not_available')

    @classmethod
    def stop_with_error(cls, context: SourceViewerContext, error: Exception) -> StepResult:
        return cls(context=context, kind='error', error=error)


__all__ = ['StepResult']
