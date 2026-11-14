"""Span completion tests for the reprocess orchestrator (#286)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.application.reprocess import Reprocess
from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.core.types import CompanyId

pytestmark = pytest.mark.unit

COMPANY = CompanyId('co1')
TRACE_ID = 't1'


class _FakeConfig:
    class Switches:
        pass


def _build_orchestrator(tracing: Any = None) -> Reprocess:
    return Reprocess(
        config=_FakeConfig(),
        document_repository=None,
        chunk_repository=None,
        vector_write=None,
        vector_store=None,
        answer_cache=None,
        job_repository=None,
        queue=None,
        metric_repository=None,
        change_event_publisher=None,
        company_repository=None,
        tracing=tracing,
        batch_size=1,
        priority='low',
    )


def test_reprocess_emits_completion_spans_with_duration_and_outcome() -> None:
    tracer = DisabledTracer()
    orchestrator = _build_orchestrator(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        result = asyncio.run(
            orchestrator.run(
                {
                    'company_ids': [str(COMPANY)],
                    'batch_size': 1,
                    'sync': True,
                }
            )
        )
        assert result is not None
        assert result.status == 'completed'

        spans = tracer.emitted_spans(str(COMPANY))
        if spans:
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


def test_reprocess_failed_step_emits_failure_span() -> None:
    tracer = DisabledTracer()

    class _FailingRepo:
        async def list_documents(self, company_id: Any) -> None:
            raise RuntimeError('repo failure')

    orchestrator = Reprocess(
        config=_FakeConfig(),
        document_repository=_FailingRepo(),
        chunk_repository=None,
        vector_write=None,
        vector_store=None,
        answer_cache=None,
        job_repository=None,
        queue=None,
        metric_repository=None,
        change_event_publisher=None,
        company_repository=None,
        tracing=tracer,
        batch_size=1,
        priority='low',
    )

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        result = asyncio.run(
            orchestrator.run(
                {
                    'company_ids': [str(COMPANY)],
                    'batch_size': 1,
                    'sync': True,
                }
            )
        )
        # One company fails but the overall flow completes with failures recorded.
        assert result is not None
        assert str(COMPANY) in result.failed_companies

        spans = tracer.emitted_spans(str(COMPANY))
        proc_spans = [s for s in spans if s.name == 'process_company']
        assert proc_spans, 'expected a process_company span'
        assert proc_spans[-1].attributes.get('outcome') == 'failure'
        assert isinstance(proc_spans[-1].attributes.get('duration_ms'), (int, float))
        assert proc_spans[-1].attributes.get('duration_ms', 0) > 0
    finally:
        reset_request_context(tokens)


def test_reprocess_without_tracer_still_works() -> None:
    orchestrator = _build_orchestrator(tracing=None)
    result = asyncio.run(
        orchestrator.run(
            {
                'company_ids': [str(COMPANY)],
                'batch_size': 1,
                'sync': True,
            }
        )
    )
    assert result is not None
    assert result.status == 'completed'
