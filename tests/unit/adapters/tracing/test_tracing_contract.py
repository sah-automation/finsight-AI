"""Contract tests for TracingPort implementations.

These tests verify that any TracingPort implementation (DisabledTracer, TracingAdapter)
behaves correctly and can be substituted without changing observable behavior.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.domain.ports.tracing_port import TracingPort
from finsight.domain.value_objects.span import Span


# Test cases that apply to ALL TracingPort implementations
class TracingPortContract:
    """Contract tests for TracingPort implementations."""

    @pytest.fixture
    def tracer(self) -> TracingPort:
        """Fixture to be overridden by concrete test classes."""
        raise NotImplementedError('Subclasses must implement tracer fixture')

    # ===== Core span emission =====

    def test_start_span_returns_span(self, tracer: TracingPort) -> None:
        """start_span returns a Span object."""
        span = asyncio.run(tracer.start_span('company_123', 'operation_name'))
        assert isinstance(span, Span)

    def test_start_span_requires_company_id(self, tracer: TracingPort) -> None:
        """start_span requires company_id as first argument."""
        # This is a design-time contract; the signature enforces it
        # Check the port's abstract method signature, not the concrete impl
        port_method = TracingPort.__dict__['start_span']
        sig = inspect.signature(port_method)
        params = list(sig.parameters.keys())
        assert params[1] == 'company_id'

    def test_start_span_includes_company_id(self, tracer: TracingPort) -> None:
        """Returned span includes the provided company_id."""
        company_id = 'test_company_456'
        span = asyncio.run(tracer.start_span(company_id, 'test_op'))
        assert span.company_id == company_id  # type: ignore[attr-defined]

    def test_start_span_sets_name_from_operation(self, tracer: TracingPort) -> None:
        """Operation name becomes span name when name not provided."""
        span = asyncio.run(tracer.start_span('co1', 'my_operation'))
        assert span.name == 'my_operation'  # type: ignore[attr-defined]

    def test_start_span_allows_explicit_name(self, tracer: TracingPort) -> None:
        """Explicit name parameter overrides operation."""
        span = asyncio.run(tracer.start_span('co1', 'operation', name='explicit_name'))
        assert span.name == 'explicit_name'  # type: ignore[attr-defined]

    def test_start_span_includes_trace_id(self, tracer: TracingPort) -> None:
        """Span includes trace_id when provided."""
        span = asyncio.run(tracer.start_span('co1', 'op', trace_id='trace_abc'))
        assert span.trace_id == 'trace_abc'  # type: ignore[attr-defined]

    def test_start_span_includes_attributes(self, tracer: TracingPort) -> None:
        """Span includes provided attributes."""
        span = asyncio.run(tracer.start_span('co1', 'op', attributes={'key': 'value'}))
        assert span.attributes.get('key') == 'value'  # type: ignore[attr-defined]

    def test_start_span_includes_metadata(self, tracer: TracingPort) -> None:
        """Span includes provided metadata."""
        span = asyncio.run(tracer.start_span('co1', 'op', metadata={'meta_key': 'meta_value'}))
        assert span.attributes.get('meta_key') == 'meta_value'  # type: ignore[attr-defined]

    # ===== Minimal/disabled mode =====

    def test_start_span_respects_active_false(self, tracer: TracingPort) -> None:
        """active=False produces minimal/disabled span."""
        span = asyncio.run(tracer.start_span('co1', 'op', active=False))
        assert span.minimal is True  # type: ignore[attr-defined]
        assert span.active is False  # type: ignore[attr-defined]

    def test_start_span_respects_enabled_false(self, tracer: TracingPort) -> None:
        """enabled=False produces minimal/disabled span."""
        span = asyncio.run(tracer.start_span('co1', 'op', enabled=False))
        assert span.minimal is True  # type: ignore[attr-defined]
        assert span.active is False  # type: ignore[attr-defined]

    def test_start_span_respects_mode_disabled(self, tracer: TracingPort) -> None:
        """mode='disabled' produces minimal/disabled span."""
        span = asyncio.run(tracer.start_span('co1', 'op', mode='disabled'))
        assert span.minimal is True  # type: ignore[attr-defined]
        assert span.active is False  # type: ignore[attr-defined]

    def test_start_span_respects_minimal_true(self, tracer: TracingPort) -> None:
        """minimal=True produces minimal span."""
        span = asyncio.run(tracer.start_span('co1', 'op', minimal=True))
        assert span.minimal is True  # type: ignore[attr-defined]
        assert span.active is False  # type: ignore[attr-defined]

    def test_disabled_span_still_has_company_id(self, tracer: TracingPort) -> None:
        """Even minimal spans include company_id."""
        span = asyncio.run(tracer.start_span('co1', 'op', active=False))
        assert span.company_id == 'co1'  # type: ignore[attr-defined]

    def test_disabled_span_has_company_hash(self, tracer: TracingPort) -> None:
        """Even minimal spans include company_hash attribute."""
        span = asyncio.run(tracer.start_span('co1', 'op', active=False))
        assert 'company_hash' in span.attributes  # type: ignore[attr-defined]

    # ===== Alias methods =====

    def test_span_alias(self, tracer: TracingPort) -> None:
        """span() alias works."""
        span = asyncio.run(tracer.span('co1', 'op'))
        assert isinstance(span, Span)

    def test_emit_span_alias(self, tracer: TracingPort) -> None:
        """emit_span() alias works."""
        span = asyncio.run(tracer.emit_span('co1', 'op'))
        assert isinstance(span, Span)

    def test_record_span_alias(self, tracer: TracingPort) -> None:
        """record_span() alias works."""
        span = asyncio.run(tracer.record_span('co1', 'op'))
        assert isinstance(span, Span)

    def test_trace_alias(self, tracer: TracingPort) -> None:
        """trace() alias works."""
        span = asyncio.run(tracer.trace('co1', 'op'))
        assert isinstance(span, Span)

    def test_trace_operation_alias(self, tracer: TracingPort) -> None:
        """trace_operation() alias works."""
        span = asyncio.run(tracer.trace_operation('co1', 'op'))
        assert isinstance(span, Span)

    def test_start_alias(self, tracer: TracingPort) -> None:
        """start() alias works."""
        span = asyncio.run(tracer.start('co1', 'op'))
        assert isinstance(span, Span)

    def test_begin_span_alias(self, tracer: TracingPort) -> None:
        """begin_span() alias works."""
        span = asyncio.run(tracer.begin_span('co1', 'op'))
        assert isinstance(span, Span)

    def test_open_span_alias(self, tracer: TracingPort) -> None:
        """open_span() alias works."""
        span = asyncio.run(tracer.open_span('co1', 'op'))
        assert isinstance(span, Span)

    def test_create_span_alias(self, tracer: TracingPort) -> None:
        """create_span() alias works."""
        span = asyncio.run(tracer.create_span('co1', 'op'))
        assert isinstance(span, Span)

    def test_emit_alias(self, tracer: TracingPort) -> None:
        """emit() alias works."""
        span = asyncio.run(tracer.emit('co1', 'op'))
        assert isinstance(span, Span)

    def test_record_alias(self, tracer: TracingPort) -> None:
        """record() alias works."""
        span = asyncio.run(tracer.record('co1', 'op'))
        assert isinstance(span, Span)

    def test_put_alias(self, tracer: TracingPort) -> None:
        """put() alias works."""
        span = asyncio.run(tracer.put('co1', 'op'))
        assert isinstance(span, Span)

    # ===== make_span =====

    def test_make_span_returns_span(self, tracer: TracingPort) -> None:
        """make_span returns a Span without emitting."""
        span = asyncio.run(tracer.make_span('co1', name='test'))
        assert isinstance(span, Span)

    def test_make_span_includes_company_id(self, tracer: TracingPort) -> None:
        """make_span includes company_id."""
        span = asyncio.run(tracer.make_span('co1', name='test'))
        assert span.company_id == 'co1'

    # ===== Company ID conversion =====

    def test_to_trace_attribute_returns_dict(self, tracer: TracingPort) -> None:
        """to_trace_attribute returns a dict with company_hash."""
        result = tracer.to_trace_attribute('test_company')
        assert isinstance(result, dict)
        assert 'company_hash' in result

    def test_convert_company_id_alias(self, tracer: TracingPort) -> None:
        """convert_company_id is an alias for to_trace_attribute."""
        result1 = tracer.to_trace_attribute('co1')
        result2 = tracer.convert_company_id('co1')
        assert result1 == result2


# ===== Concrete test classes for each implementation =====


class TestDisabledTracerContract(TracingPortContract):
    """Contract tests for DisabledTracer."""

    @pytest.fixture
    def tracer(self) -> TracingPort:
        return DisabledTracer()


class TestTracingAdapterContract(TracingPortContract):
    """Contract tests for TracingAdapter."""

    @pytest.fixture
    def tracer(self) -> TracingPort:
        return TracingAdapter(service_name='test', enabled=True)


# ===== Implementation-specific tests =====


class TestDisabledTracerRecords:
    """Tests for DisabledTracer record methods."""

    def test_records_returns_list(self) -> None:
        """records() returns a list of span dicts."""
        tracer = DisabledTracer()
        asyncio.run(tracer.start_span('co1', 'op1'))
        asyncio.run(tracer.start_span('co1', 'op2'))
        records = tracer.records('co1')
        assert isinstance(records, list)
        assert len(records) == 2

    def test_emitted_spans_returns_list(self) -> None:
        """emitted_spans() returns a list of Span objects."""
        tracer = DisabledTracer()
        asyncio.run(tracer.start_span('co1', 'op1'))
        spans = tracer.emitted_spans('co1')
        assert isinstance(spans, list)
        assert len(spans) == 1
        assert all(isinstance(s, Span) for s in spans)

    def test_records_filters_by_company(self) -> None:
        """records() filters by company_id."""
        tracer = DisabledTracer()
        asyncio.run(tracer.start_span('co1', 'op1'))
        asyncio.run(tracer.start_span('co2', 'op2'))
        records = tracer.records('co1')
        assert len(records) == 1
        assert records[0]['company_id'] == 'co1'


class TestTracingAdapterRecords:
    """Tests for TracingAdapter record methods."""

    def test_records_returns_list(self) -> None:
        """records() returns a list of span dicts."""
        tracer = TracingAdapter(service_name='test', enabled=True)
        asyncio.run(tracer.start_span('co1', 'op1'))
        asyncio.run(tracer.start_span('co1', 'op2'))
        records = tracer.records('co1')
        assert isinstance(records, list)
        assert len(records) == 2

    def test_emitted_spans_returns_list(self) -> None:
        """emitted_spans() returns a list of Span objects."""
        tracer = TracingAdapter(service_name='test', enabled=True)
        asyncio.run(tracer.start_span('co1', 'op1'))
        spans = tracer.emitted_spans('co1')
        assert isinstance(spans, list)
        assert len(spans) == 1
        assert all(isinstance(s, Span) for s in spans)

    def test_records_filters_by_company(self) -> None:
        """records() filters by company_id."""
        tracer = TracingAdapter(service_name='test', enabled=True)
        asyncio.run(tracer.start_span('co1', 'op1'))
        asyncio.run(tracer.start_span('co2', 'op2'))
        records = tracer.records('co1')
        assert len(records) == 1
        assert records[0]['company_id'] == 'co1'


# ===== Substitutability tests =====


class TestTracingSubstitutability:
    """Tests verifying that implementations are substitutable."""

    def test_both_implement_tracing_port(self) -> None:
        """Both implementations satisfy the TracingPort interface."""
        disabled = DisabledTracer()
        active = TracingAdapter(service_name='test', enabled=True)

        assert isinstance(disabled, TracingPort)
        assert isinstance(active, TracingPort)

    def test_same_method_signatures(self) -> None:
        """Both implementations have the same public method signatures."""
        disabled = DisabledTracer()
        active = TracingAdapter(service_name='test', enabled=True)

        _non_callable_public = {
            'otel',
            'otel_exporter',
            'otel_provider',
            'otel_processor',
            'otel_tracer',
            'exporter',
            'provider',
            'processor',
            'tracer',
            'spans',
        }
        for name in dir(disabled):
            if not name.startswith('_') and name not in _non_callable_public:
                assert hasattr(active, name), f'Missing {name} on TracingAdapter'
                assert callable(getattr(disabled, name))
                assert callable(getattr(active, name))

    @pytest.mark.parametrize(
        'tracer_factory',
        [
            DisabledTracer,
            lambda: TracingAdapter(service_name='test', enabled=True),
        ],
    )
    def test_span_emission_always_returns_span(
        self, tracer_factory: Callable[[], TracingPort]
    ) -> None:
        """All implementations return a Span from start_span."""
        tracer = tracer_factory()
        span = asyncio.run(tracer.start_span('co1', 'op'))
        assert isinstance(span, Span)

    @pytest.mark.parametrize(
        'tracer_factory',
        [
            DisabledTracer,
            lambda: TracingAdapter(service_name='test', enabled=True),
        ],
    )
    def test_disabled_mode_produces_minimal_span(
        self, tracer_factory: Callable[[], TracingPort]
    ) -> None:
        """All implementations produce minimal spans in disabled mode."""
        tracer = tracer_factory()
        span = asyncio.run(tracer.start_span('co1', 'op', active=False))
        assert span.minimal is True  # type: ignore[attr-defined]
        assert span.active is False  # type: ignore[attr-defined]
