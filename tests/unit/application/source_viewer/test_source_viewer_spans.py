"""Span completion tests for the source-viewer orchestrator (#286)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.application.source_viewer import SourceViewer
from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.step_result import StepResult
from finsight.core.logging.context import bind_request_context, reset_request_context

pytestmark = pytest.mark.unit

COMPANY = 'co1'
TRACE_ID = 't1'


class _OkStep:
    async def run(self, context: Any) -> StepResult:
        return StepResult.continue_(context)


class _FailingStep:
    async def run(self, context: Any) -> StepResult:
        raise RuntimeError('step failure')


def _build_viewer(tracing: Any = None, failing_step: bool = False) -> SourceViewer:
    step_cls = _FailingStep if failing_step else _OkStep
    return SourceViewer(
        authorize_step=step_cls(),
        resolve_citation_step=step_cls(),
        resolve_version_step=step_cls(),
        fetch_content_step=step_cls(),
        fetch_original_step=step_cls(),
        audit_step=step_cls(),
        tracing=tracing,
    )


def test_source_viewer_emits_completion_spans_with_duration_and_outcome() -> None:
    tracer = DisabledTracer()
    viewer = _build_viewer(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, COMPANY, 'u1')
    try:
        ctx = SourceViewerContext(
            company_id=COMPANY,
            document_id='doc1',
            page=1,
        )
        result = asyncio.run(viewer.run(ctx))
        assert result.status == 'available'

        spans = tracer.emitted_spans(COMPANY)
        assert spans, 'expected at least one span'
        for span in spans:
            attrs = span.attributes
            assert isinstance(attrs.get('duration_ms'), (int, float)), (
                f'missing duration_ms in {span.name}'
            )
            assert attrs.get('duration_ms', 0) > 0
            assert attrs.get('outcome') == 'success'
            assert attrs.get('trace_id') == TRACE_ID
    finally:
        reset_request_context(tokens)


def test_source_viewer_failed_step_emits_failure_span() -> None:
    tracer = DisabledTracer()
    viewer = _build_viewer(tracing=tracer, failing_step=True)

    tokens = bind_request_context(TRACE_ID, COMPANY, 'u1')
    try:
        ctx = SourceViewerContext(
            company_id=COMPANY,
            document_id='doc1',
            page=1,
        )
        result = asyncio.run(viewer.run(ctx))
        # A failing step stops the pipeline with a not_available status and error outcome.
        assert result.status == 'not_available'
        assert result.outcome == 'error'

        spans = tracer.emitted_spans(COMPANY)
        auth_spans = [s for s in spans if s.name == 'authorize']
        assert auth_spans, 'expected an authorize span'
        assert auth_spans[-1].attributes.get('outcome') == 'failure'
        assert isinstance(auth_spans[-1].attributes.get('duration_ms'), (int, float))
        assert auth_spans[-1].attributes.get('duration_ms', 0) > 0
    finally:
        reset_request_context(tokens)


def test_source_viewer_without_tracer_still_works() -> None:
    viewer = _build_viewer(tracing=None)
    ctx = SourceViewerContext(company_id=COMPANY, document_id='doc1', page=1)
    result = asyncio.run(viewer.run(ctx))
    assert result.status == 'available'
