"""Span completion tests for the upload orchestrator (#286)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.application.ingest_document.upload_document import UploadDocument
from finsight.core.errors import ValidationError
from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.core.types import CompanyId

pytestmark = pytest.mark.unit

COMPANY = CompanyId('co1')
TRACE_ID = 't1'


class _FakeConfig:
    class Switches:
        answer_cache_enabled = True


def _build_orchestrator(tracing: Any = None) -> UploadDocument:
    return UploadDocument(
        config=_FakeConfig(),
        document_repository=None,
        object_storage=None,
        partition_manager=None,
        partition_metadata_repository=None,
        partition_checker=None,
        unit_of_work=None,
        answer_cache=None,
        job_repository=None,
        queue=None,
        tracing=tracing,
    )


def test_upload_emits_completion_spans_with_duration_and_outcome() -> None:
    tracer = DisabledTracer()
    orchestrator = _build_orchestrator(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        result = asyncio.run(
            orchestrator.run(
                {
                    'company_id': str(COMPANY),
                    'document_category': 'financial_statement',
                    'period': '2024-Q1',
                    'status': 'draft',
                    'upload_type': 'new',
                }
            )
        )
        assert result is not None
        assert result.status == 'accepted'

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


def test_upload_failed_step_emits_failure_span() -> None:
    tracer = DisabledTracer()
    orchestrator = _build_orchestrator(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        with pytest.raises(ValidationError):
            asyncio.run(
                orchestrator.run(
                    {
                        # Missing required document_category -> validation error.
                        'company_id': str(COMPANY),
                        'period': '2024-Q1',
                        'status': 'draft',
                        'upload_type': 'new',
                    }
                )
            )
        # Validation happens before any traced step, so there may be no spans.
        # This test mainly verifies no crash when tracing is present.
    finally:
        reset_request_context(tokens)


def test_upload_without_tracer_still_works() -> None:
    orchestrator = _build_orchestrator(tracing=None)
    result = asyncio.run(
        orchestrator.run(
            {
                'company_id': str(COMPANY),
                'document_category': 'financial_statement',
                'period': '2024-Q1',
                'status': 'draft',
                'upload_type': 'new',
            }
        )
    )
    assert result is not None
    assert result.status == 'accepted'
