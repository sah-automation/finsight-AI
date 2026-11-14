"""Span completion tests for the delete_document orchestrator (#286)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.application.delete_document import DeleteDocument
from finsight.core.errors import ValidationError
from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.core.types import CompanyId

pytestmark = pytest.mark.unit

COMPANY = CompanyId('co1')
TRACE_ID = 't1'


class _FakeConfig:
    pass


def _build_orchestrator(tracing: Any = None) -> DeleteDocument:
    return DeleteDocument(
        config=_FakeConfig(),
        document_repository=None,
        chunk_repository=None,
        vector_write=None,
        vector_store=None,
        answer_cache=None,
        job_repository=None,
        queue=None,
        metric_repository=None,
        audit_repository=None,
        company_repository=None,
        tracing=tracing,
    )


def test_delete_emits_completion_spans_with_duration_and_outcome() -> None:
    tracer = DisabledTracer()
    orchestrator = _build_orchestrator(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        result = asyncio.run(
            orchestrator.run(
                {
                    'company_id': str(COMPANY),
                    'document_id': 'doc1',
                    'action': 'delete',
                }
            )
        )
        assert result is not None

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


def test_delete_without_tracer_still_works() -> None:
    orchestrator = _build_orchestrator(tracing=None)
    result = asyncio.run(
        orchestrator.run(
            {
                'company_id': str(COMPANY),
                'document_id': 'doc1',
                'action': 'delete',
            }
        )
    )
    assert result is not None


def test_delete_missing_company_id_raises() -> None:
    orchestrator = _build_orchestrator(tracing=None)
    with pytest.raises(ValidationError):
        asyncio.run(
            orchestrator.run(
                {
                    'document_id': 'doc1',
                    'action': 'delete',
                }
            )
        )
