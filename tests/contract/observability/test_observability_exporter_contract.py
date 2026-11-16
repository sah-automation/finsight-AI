"""Contract tests for the ObservabilityExporter port.

Both CloudWatchExporter (pilot) and OtlpEndpointExporter (standard)
must pass this identical test suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

if TYPE_CHECKING:
    from finsight.domain.ports.observability import ObservabilityExporterPort


pytestmark = pytest.mark.contract


class DummySpan:
    """Minimal span for testing."""

    def __init__(self, name: str = 'test-span', attributes: dict | None = None):
        self.name = name
        self.attributes = attributes or {}
        self.span_name = name
        self.operation = name
        self.trace_id = 'test-trace-id'


class TestObservabilityExporterContract:
    """Contract tests that all ObservabilityExporterPort implementations must pass."""

    @pytest.fixture
    def cloudwatch_exporter(self) -> ObservabilityExporterPort:
        from finsight.adapters.observability import CloudWatchExporter

        with mock.patch('finsight.adapters.tracing._tracing_otel.OTLPSpanExporter'):
            exporter = CloudWatchExporter(
                endpoint='https://logs.us-east-1.amazonaws.com/v1/logs',
                headers={
                    'x-aws-logs-group': '/aws/lambda/test',
                    'x-aws-logs-stream': 'test-stream',
                },
                sample_rate=1.0,
                service_name='test-service',
            )
            # Force enabled for testing
            exporter._enabled = True
            yield exporter

    @pytest.fixture
    def otlp_endpoint_exporter(self) -> ObservabilityExporterPort:
        from finsight.adapters.observability import OtlpEndpointExporter

        with mock.patch('finsight.adapters.tracing._tracing_otel.OTLPSpanExporter'):
            exporter = OtlpEndpointExporter(
                endpoint='https://otel.example.com/v1/traces',
                headers={'authorization': 'Bearer test-token'},
                sample_rate=1.0,
                service_name='test-service',
            )
            # Force enabled for testing
            exporter._enabled = True
            yield exporter

    @pytest.fixture(params=['cloudwatch_exporter', 'otlp_endpoint_exporter'])
    def exporter(self, request: pytest.FixtureRequest) -> ObservabilityExporterPort:
        """Parametrized fixture that yields each exporter implementation."""
        return request.getfixturevalue(request.param)

    def test_exports_span(self, exporter: ObservabilityExporterPort) -> None:
        """Exporter can export a span without error."""
        span = DummySpan(name='test-operation', attributes={'key': 'value'})
        exporter.export_span(span)
        # No exception means success

    def test_flush_completes(self, exporter: ObservabilityExporterPort) -> None:
        """Flush completes without error."""
        exporter.flush()
        # No exception means success

    def test_shutdown_completes(self, exporter: ObservabilityExporterPort) -> None:
        """Shutdown completes without error and releases resources."""
        exporter.shutdown()
        # No exception means success
        # After shutdown, exporter should be disabled
        assert not exporter.enabled

    def test_has_backend_name(self, exporter: ObservabilityExporterPort) -> None:
        """Exporter reports its backend name."""
        assert hasattr(exporter, 'backend_name')
        assert isinstance(exporter.backend_name, str)
        assert exporter.backend_name in ('cloudwatch', 'otlp_endpoint')

    def test_has_endpoint_property(self, exporter: ObservabilityExporterPort) -> None:
        """Exporter exposes its endpoint."""
        assert hasattr(exporter, 'endpoint')
        assert isinstance(exporter.endpoint, str)
        assert exporter.endpoint.startswith('http')

    def test_has_headers_property(self, exporter: ObservabilityExporterPort) -> None:
        """Exporter exposes its headers."""
        assert hasattr(exporter, 'headers')
        assert isinstance(exporter.headers, dict)

    def test_has_sample_rate_property(self, exporter: ObservabilityExporterPort) -> None:
        """Exporter exposes its sample rate."""
        assert hasattr(exporter, 'sample_rate')
        assert isinstance(exporter.sample_rate, float)
        assert 0.0 <= exporter.sample_rate <= 1.0

    def test_enabled_property(self, exporter: ObservabilityExporterPort) -> None:
        """Exporter reports enabled status."""
        assert hasattr(exporter, 'enabled')
        assert isinstance(exporter.enabled, bool)

    def test_multiple_exports_work(self, exporter: ObservabilityExporterPort) -> None:
        """Multiple span exports work correctly."""
        for i in range(5):
            span = DummySpan(name=f'operation-{i}', attributes={'index': i})
            exporter.export_span(span)
        exporter.flush()

    def test_shutdown_idempotent(self, exporter: ObservabilityExporterPort) -> None:
        """Shutdown can be called multiple times without error."""
        exporter.shutdown()
        exporter.shutdown()  # Second call should not raise
        assert not exporter.enabled

    def test_backend_name_matches_expected(self, exporter: ObservabilityExporterPort) -> None:
        """Backend name matches the expected value for each implementation."""
        if exporter.__class__.__name__ == 'CloudWatchExporter':
            assert exporter.backend_name == 'cloudwatch'
        elif exporter.__class__.__name__ == 'OtlpEndpointExporter':
            assert exporter.backend_name == 'otlp_endpoint'


__all__ = ['TestObservabilityExporterContract']
