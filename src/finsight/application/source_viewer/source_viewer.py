"""Thin orchestrator for the six-step source-viewer pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from finsight.application._step_span import run_traced_step

from ._request_to_context import _build_source_viewer_context
from ._result import build_source_viewer_result
from .source_viewer_context import SourceViewerContext
from .step_result import StepResult

if TYPE_CHECKING:
    from finsight.domain.ports.tracing_port import TracingPort

    from .models import SourceViewerResult
    from .steps import (
        AuditStep,
        AuthorizeStep,
        FetchContentStep,
        FetchOriginalStep,
        ResolveCitationStep,
        ResolveVersionStep,
    )

logger = logging.getLogger(__name__)

_STEP_ORDER = (
    ('authorize', 'authorize_step'),
    ('resolve_citation', 'resolve_citation_step'),
    ('resolve_version', 'resolve_version_step'),
    ('fetch_content', 'fetch_content_step'),
    ('fetch_original', 'fetch_original_step'),
)


class SourceViewer:
    """Run the source-viewer steps in sequence and build the result."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        authorize_step: AuthorizeStep,
        resolve_citation_step: ResolveCitationStep,
        resolve_version_step: ResolveVersionStep,
        fetch_content_step: FetchContentStep,
        fetch_original_step: FetchOriginalStep,
        audit_step: AuditStep,
        tracing: TracingPort | None = None,
    ) -> None:
        self._authorize_step = authorize_step
        self._resolve_citation_step = resolve_citation_step
        self._resolve_version_step = resolve_version_step
        self._fetch_content_step = fetch_content_step
        self._fetch_original_step = fetch_original_step
        self._audit_step = audit_step
        self._tracing = tracing

    async def run(
        self,
        context: SourceViewerContext | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SourceViewerResult:
        """Run the pipeline for the given context or request payload."""
        ctx = self._coerce_context(context, kwargs)
        initial = {
            'document_id': ctx.document_id,
            'page': ctx.page,
            'citation': ctx.citation_input,
            'version_id': ctx.version_id,
            'company_id': ctx.company_id,
        }
        outcome = await self._run_steps(ctx)
        await self._run_audit(ctx, outcome)
        return build_source_viewer_result(ctx, outcome, initial)

    async def _run_steps(self, context: SourceViewerContext) -> str:
        for operation, attribute in _STEP_ORDER:
            step = getattr(self, f'_{attribute}')

            async def _run_step(op: str = operation, s: Any = step) -> Any:
                return await s.run(context)

            try:
                result = await run_traced_step(
                    self._tracing, context.company_id, operation, _run_step
                )
            except Exception as exc:  # noqa: BLE001, pragma: no cover
                result = StepResult.stop_with_error(context, exc)
            if not isinstance(result, StepResult):
                continue
            if result.kind == 'not_available':
                return 'not_available'
            if result.kind == 'error':
                return 'error'
        return 'success'

    async def _run_audit(self, context: SourceViewerContext, outcome: str) -> None:
        await run_traced_step(
            self._tracing,
            context.company_id,
            'audit',
            lambda: self._run_audit_step(context, outcome),
        )

    async def _run_audit_step(self, context: SourceViewerContext, outcome: str) -> None:
        context.outcome = outcome
        try:
            await self._audit_step.run(context)
        except Exception as exc:
            logger.debug('audit step failed', exc_info=exc)

    def _coerce_context(
        self, context: SourceViewerContext | dict[str, Any] | None, kwargs: dict[str, Any]
    ) -> SourceViewerContext:
        if isinstance(context, SourceViewerContext):
            return context
        if context is None:
            return _build_source_viewer_context(**kwargs)
        return _build_source_viewer_context(context, **kwargs)
