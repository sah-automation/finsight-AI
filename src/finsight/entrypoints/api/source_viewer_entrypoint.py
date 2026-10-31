"""Compatibility entrypoint alias for source viewer."""

from __future__ import annotations

from typing import Any

from finsight.entrypoints.api.source_viewer import _handle


class SourceViewerEntrypoint:
    def __init__(
        self, use_case: Any = None, context: Any = None, role: Any = None, **deps: Any
    ) -> None:
        self.use_case = use_case
        self.context = context
        self.role = role
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if (
            self.use_case is not None
            and 'use_case' not in kwargs
            and 'source_viewer_use_case' not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('source_viewer_use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.role is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('role', self.role)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


# aliases
SourceViewerHandler = SourceViewerEntrypoint
SourceViewerEndpoint = SourceViewerEntrypoint
SourceViewerAPI = SourceViewerEntrypoint
SourceViewEntrypoint = SourceViewerEntrypoint
SourceEndpoint = SourceViewerEntrypoint
DocumentsSourceEntrypoint = SourceViewerEntrypoint
SourceViewer = SourceViewerEntrypoint
ViewSource = SourceViewerEntrypoint
SourceView = SourceViewerEntrypoint
Source = SourceViewerEntrypoint
