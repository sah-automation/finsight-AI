"""Unit tests for SourceViewerContext and StepResult."""

from __future__ import annotations

from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.step_result import StepResult


def test_source_viewer_context_defaults() -> None:
    context = SourceViewerContext()
    assert context.company_id is None
    assert context.result_obj is None
    assert context.outcome is None
    assert context.tables == []
    assert context.extras == {}


def test_step_result_constructors() -> None:
    context = SourceViewerContext()
    continue_result = StepResult.continue_(context)
    assert continue_result.kind == 'continue'
    assert continue_result.context is context

    not_available = StepResult.stop_with_not_available(context)
    assert not_available.kind == 'not_available'

    error = ValueError('boom')
    errored = StepResult.stop_with_error(context, error)
    assert errored.kind == 'error'
    assert errored.error is error
