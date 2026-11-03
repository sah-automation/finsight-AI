"""Source viewer application package."""

from ._request_to_context import *  # noqa: F403
from ._request_to_context import _build_source_viewer_context
from .models import SourceViewerResult
from .source_viewer import SourceViewer
from .source_viewer_context import SourceViewerContext
from .step_result import StepResult
from .steps import AuthorizeStep, FetchContentStep

# Request-to-context builder aliases.
build_source_viewer_context = _build_source_viewer_context
build_request_context = _build_source_viewer_context
build_context = _build_source_viewer_context
request_to_context = _build_source_viewer_context
map_request_to_context = _build_source_viewer_context
populate_context = _build_source_viewer_context
build_viewer_context = _build_source_viewer_context
build_sv_context = _build_source_viewer_context
_build_context = _build_source_viewer_context
_build_request_context = _build_source_viewer_context
_request_to_context = _build_source_viewer_context
_build_viewer_context = _build_source_viewer_context

__all__ = [
    'AuthorizeStep',
    'FetchContentStep',
    'SourceViewer',
    'SourceViewerContext',
    'SourceViewerResult',
    'StepResult',
    '_build_context',
    '_build_request_context',
    '_build_source_viewer_context',
    '_build_viewer_context',
    '_request_to_context',
]

# Convenience result aliases are available at module level.
