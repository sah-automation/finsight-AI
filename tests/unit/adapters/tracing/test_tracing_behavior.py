"""Behavioral tests for tracing adapter."""

from __future__ import annotations

import asyncio

from finsight.adapters.tracing.tracing_adapter import TracingAdapter


def test_tracing_adapter_records_span() -> None:
    tracer = TracingAdapter(service_name='test', enabled=True)
    span = asyncio.run(tracer.start_span('co1', 'model_generation', attributes={'model_name': 'm'}))
    assert getattr(span, 'company_id', None) is not None
    assert len(tracer.records('co1')) == 1
    assert len(tracer.emitted_spans('co1')) == 1
