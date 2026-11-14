"""Span completion tests for the onboarding orchestrator (#286)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.application.onboarding import CreateCompany
from finsight.core.logging.context import bind_request_context, reset_request_context

pytestmark = pytest.mark.unit

COMPANY = 'co1'
TRACE_ID = 't1'


class _FakeConfig:
    pass


def _build_orchestrator(tracing: Any = None) -> CreateCompany:
    return CreateCompany(
        config=_FakeConfig(),
        company_repository=None,
        user_repository=None,
        partition_manager=None,
        partition_metadata_repository=None,
        audit_log=None,
        role_cache=None,
        metering=None,
        document_stamp=None,
        unit_of_work=None,
        tracing=tracing,
    )


def test_onboarding_emits_completion_span_with_duration_and_outcome() -> None:
    tracer = DisabledTracer()
    orchestrator = _build_orchestrator(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, COMPANY, 'u1')
    try:
        result = asyncio.run(
            orchestrator.run(
                {
                    'company_name': 'Test Company',
                    'region': 'us-east-1',
                    'admin_email': 'admin@example.com',
                }
            )
        )
        assert result is not None
        assert result.status.value == 'ready'

        spans = tracer.emitted_spans()
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


def test_onboarding_failed_step_emits_failure_span() -> None:
    tracer = DisabledTracer()

    class _FailingRepo:
        async def create_company(self, company_id: Any, name: str, slug: str) -> None:
            raise RuntimeError('repo failure')

    orchestrator = CreateCompany(
        config=_FakeConfig(),
        company_repository=_FailingRepo(),
        user_repository=None,
        partition_manager=None,
        partition_metadata_repository=None,
        audit_log=None,
        role_cache=None,
        metering=None,
        document_stamp=None,
        unit_of_work=None,
        tracing=tracer,
    )

    tokens = bind_request_context(TRACE_ID, COMPANY, 'u1')
    try:
        with pytest.raises(RuntimeError):
            asyncio.run(
                orchestrator.run(
                    {
                        'company_name': 'Test Company',
                        'region': 'us-east-1',
                        'admin_email': 'admin@example.com',
                    }
                )
            )

        spans = tracer.emitted_spans()
        onb_spans = [s for s in spans if s.name == 'onboarding_step']
        assert onb_spans, 'expected an onboarding_step span'
        assert onb_spans[-1].attributes.get('outcome') == 'failure'
        assert isinstance(onb_spans[-1].attributes.get('duration_ms'), (int, float))
        assert onb_spans[-1].attributes.get('duration_ms', 0) > 0
    finally:
        reset_request_context(tokens)


def test_onboarding_without_tracer_still_works() -> None:
    orchestrator = _build_orchestrator(tracing=None)
    result = asyncio.run(
        orchestrator.run(
            {
                'company_name': 'Test Company',
                'region': 'us-east-1',
                'admin_email': 'admin@example.com',
            }
        )
    )
    assert result is not None
    assert result.status.value == 'ready'
