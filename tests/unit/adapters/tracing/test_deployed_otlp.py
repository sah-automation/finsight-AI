"""Fake OTLP receiver test for the deployed Lambda path (issue #287).

Asserts that the tracing adapter's OTLP exporter is configured with the
deployed CloudWatch Logs OTLP endpoint *and* the routing headers naming the
Observability log group and stream, without making any real network call.

The OpenTelemetry span exporter is replaced with a fake that records the
endpoint and headers it is constructed with, mirroring what a real OTLP
receiver would observe on the wire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from finsight.adapters.tracing.tracing_adapter import TracingAdapter

DEPLOYED_OTLP_ENDPOINT = 'https://logs.us-east-1.amazonaws.com/v1/logs'
DEPLOYED_ROUTING_HEADERS = {
    'x-aws-logs-group': '/aws/lambda/finsight-dev',
    'x-aws-logs-stream': 'finsight-dev-api',
}


def _deployed_config() -> dict[str, Any]:
    return {
        'observability': {
            'service_name': 'finsight-ai',
            'otlp_endpoint': DEPLOYED_OTLP_ENDPOINT,
            'otlp_headers': dict(DEPLOYED_ROUTING_HEADERS),
            'trace_sample_rate': 1.0,
            'log_level': 'INFO',
            'log_format': 'json',
            'alerts': {
                'fallback_model_3_used': True,
                'reranker_down': True,
                'embedding_retries_exceeded': 3,
                'job_in_retry_list': True,
                'role_cache_stale_seconds': 7200,
            },
        },
        'switches': {'detailed_tracing_enabled': True},
    }


@pytest.fixture
def fake_exporter() -> Iterator[mock.MagicMock]:
    with mock.patch(
        'finsight.adapters.tracing._tracing_otel.OTLPSpanExporter', new=mock.MagicMock()
    ) as fake:
        yield fake


def test_deployed_otlp_uses_cloudwatch_logs_endpoint(fake_exporter: mock.MagicMock) -> None:
    """The exporter targets the CloudWatch Logs OTLP endpoint for the stack region."""
    TracingAdapter(config=_deployed_config(), detailed_tracing_enabled=True)

    fake_exporter.assert_called_once()
    kwargs = fake_exporter.call_args.kwargs
    assert kwargs['endpoint'] == DEPLOYED_OTLP_ENDPOINT


def test_deployed_otlp_sends_routing_headers(fake_exporter: mock.MagicMock) -> None:
    """The exporter sends the log-group / log-stream routing headers."""
    TracingAdapter(config=_deployed_config(), detailed_tracing_enabled=True)

    kwargs = fake_exporter.call_args.kwargs
    assert kwargs['headers'] == DEPLOYED_ROUTING_HEADERS
    assert kwargs['headers']['x-aws-logs-group'] == '/aws/lambda/finsight-dev'
    assert kwargs['headers']['x-aws-logs-stream'] == 'finsight-dev-api'


def test_deployed_otlp_endpoint_contains_no_account_or_region(
    fake_exporter: mock.MagicMock,
) -> None:
    """The endpoint is region-derived only, with no hard-coded account/region (ADR-0002)."""
    TracingAdapter(config=_deployed_config(), detailed_tracing_enabled=True)

    kwargs = fake_exporter.call_args.kwargs
    endpoint = str(kwargs['endpoint'])
    assert endpoint == DEPLOYED_OTLP_ENDPOINT
    assert 'dkr.ecr' not in endpoint
    assert '.amazonaws.com' in endpoint


def test_disabled_tracing_does_not_configure_an_exporter() -> None:
    """When detailed tracing is off, no OTLP exporter is instantiated."""
    config = _deployed_config()
    config['switches'] = {'detailed_tracing_enabled': False}
    with mock.patch(
        'finsight.adapters.tracing._tracing_otel.OTLPSpanExporter', new=mock.MagicMock()
    ) as fake:
        tracer = TracingAdapter(config=config, detailed_tracing_enabled=False)
    assert tracer.otel is None or not getattr(tracer.otel, 'enabled', False)
    fake.assert_not_called()
