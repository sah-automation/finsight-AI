"""Source viewer application package."""

from .models import Result, SourceViewerResult, SourceViewResult, ViewResult
from .source_viewer import SourceViewer

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
    'SourceViewerFlow',
    'SourceViewerHandler',
    'SourceViewerResult',
    'SourceViewerService',
    'SourceViewerUseCase',
    'ViewResult',
    'ViewSource',
]

# Convenience result aliases are available at module level.
