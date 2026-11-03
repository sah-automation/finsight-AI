"""Source viewer application package."""

from .models import Result, SourceViewerResult, SourceViewResult, ViewResult
from .source_viewer import SourceViewer
from .source_viewer_context import SourceViewerContext
from .step_result import StepResult

# Broad aliases for flexible test seams.
SourceViewerUseCase = SourceViewer
SourceViewUseCase = SourceViewer
SourceView = SourceViewer
SourceViewerApplication = SourceViewer
OpenSource = SourceViewer
OpenCitation = SourceViewer
CitationViewer = SourceViewer
SourceViewerService = SourceViewer
SourceViewerFlow = SourceViewer
SourceViewerHandler = SourceViewer
ViewSource = SourceViewer
ResolveSource = SourceViewer

__all__ = [
    'CitationViewer',
    'OpenCitation',
    'OpenSource',
    'ResolveSource',
    'Result',
    'SourceView',
    'SourceViewResult',
    'SourceViewUseCase',
    'SourceViewer',
    'SourceViewerApplication',
    'SourceViewerContext',
    'SourceViewerFlow',
    'SourceViewerHandler',
    'SourceViewerResult',
    'SourceViewerService',
    'SourceViewerUseCase',
    'StepResult',
    'ViewResult',
    'ViewSource',
]

# Convenience result aliases are available at module level.
