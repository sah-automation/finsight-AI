"""Tests for the observability_backend config switch.

Verifies both ON (cloudwatch) and OFF (otlp_endpoint) paths work correctly.
"""

from __future__ import annotations

import pytest

from finsight.adapters.tracing._tracing_config import _observability
from finsight.core.config.models import ObservabilityConfig, SwitchesConfig


def _base_alerts() -> dict:
    return {
        'fallback_model_3_used': True,
        'reranker_down': True,
        'embedding_retries_exceeded': 3,
        'job_in_retry_list': True,
        'role_cache_stale_seconds': 7200,
    }


class TestObservabilityBackendSwitch:
    """Tests for the observability_backend switch."""

    def test_cloudwatch_backend_on(self) -> None:
        """When observability_backend is 'cloudwatch', CloudWatch endpoints are used."""
        switches = SwitchesConfig(observability_backend='cloudwatch')
        observability = ObservabilityConfig(
            log_level='INFO',
            log_format='json',
            trace_sample_rate=1.0,
            service_name='test-service',
            cloudwatch_otlp_endpoint='https://logs.us-east-1.amazonaws.com/v1/logs',
            cloudwatch_otlp_headers={'x-aws-logs-group': '/aws/lambda/test'},
            otlp_endpoint_endpoint='https://otel.example.com/v1/traces',
            otlp_endpoint_headers={'authorization': 'Bearer token'},
            alerts=_base_alerts(),
        )

        # The config should have the cloudwatch backend selected
        assert switches.observability_backend == 'cloudwatch'
        assert (
            observability.get_endpoint_for_backend('cloudwatch')
            == 'https://logs.us-east-1.amazonaws.com/v1/logs'
        )
        assert observability.get_headers_for_backend('cloudwatch') == {
            'x-aws-logs-group': '/aws/lambda/test'
        }

    def test_otlp_endpoint_backend_on(self) -> None:
        """When observability_backend is 'otlp_endpoint', OTLP endpoints are used."""
        switches = SwitchesConfig(observability_backend='otlp_endpoint')
        observability = ObservabilityConfig(
            log_level='INFO',
            log_format='json',
            trace_sample_rate=1.0,
            service_name='test-service',
            cloudwatch_otlp_endpoint='https://logs.us-east-1.amazonaws.com/v1/logs',
            cloudwatch_otlp_headers={'x-aws-logs-group': '/aws/lambda/test'},
            otlp_endpoint_endpoint='https://otel.example.com/v1/traces',
            otlp_endpoint_headers={'authorization': 'Bearer token'},
            alerts=_base_alerts(),
        )

        # The config should have the otlp_endpoint backend selected
        assert switches.observability_backend == 'otlp_endpoint'
        assert (
            observability.get_endpoint_for_backend('otlp_endpoint')
            == 'https://otel.example.com/v1/traces'
        )
        assert observability.get_headers_for_backend('otlp_endpoint') == {
            'authorization': 'Bearer token'
        }

    def test_observability_backend_off(self) -> None:
        """OFF path: observability_backend defaults to cloudwatch when not explicitly set to otlp_endpoint."""
        # Default is cloudwatch
        switches = SwitchesConfig()
        assert switches.observability_backend == 'cloudwatch'

        # Explicitly set to cloudwatch (OFF for otlp_endpoint)
        switches = SwitchesConfig(observability_backend='cloudwatch')
        assert switches.observability_backend == 'cloudwatch'

    def test_fallback_to_legacy_endpoint(self) -> None:
        """When backend-specific endpoints are not set, falls back to legacy otlp_endpoint."""
        SwitchesConfig(observability_backend='cloudwatch')
        observability = ObservabilityConfig(
            log_level='INFO',
            log_format='json',
            trace_sample_rate=1.0,
            service_name='test-service',
            otlp_endpoint='https://legacy.example.com/v1/traces',
            otlp_headers={'x-legacy': 'header'},
            alerts=_base_alerts(),
        )

        # Should fall back to legacy endpoint
        assert (
            observability.get_endpoint_for_backend('cloudwatch')
            == 'https://legacy.example.com/v1/traces'
        )
        assert observability.get_headers_for_backend('cloudwatch') == {'x-legacy': 'header'}

    def test_invalid_backend_fails_validation(self) -> None:
        """Invalid observability_backend value should fail validation."""
        with pytest.raises(ValueError):
            SwitchesConfig(observability_backend='invalid_backend')  # type: ignore[arg-type]

    def test_tracing_adapter_uses_correct_backend(self) -> None:
        """Tracing adapter should use the correct backend based on switch."""
        # Test cloudwatch backend
        config = {
            'switches': {'observability_backend': 'cloudwatch'},
            'observability': {
                'service_name': 'test',
                'cloudwatch_otlp_endpoint': 'https://logs.us-east-1.amazonaws.com/v1/logs',
                'cloudwatch_otlp_headers': {'x-aws-logs-group': '/aws/lambda/test'},
                'trace_sample_rate': 1.0,
            },
        }
        obs = _observability(config)
        assert obs['observability_backend'] == 'cloudwatch'
        assert obs['otlp_endpoint'] == 'https://logs.us-east-1.amazonaws.com/v1/logs'
        assert obs['otlp_headers'] == {'x-aws-logs-group': '/aws/lambda/test'}

        # Test otlp_endpoint backend
        config['switches']['observability_backend'] = 'otlp_endpoint'
        config['observability']['otlp_endpoint_endpoint'] = 'https://otel.example.com/v1/traces'
        config['observability']['otlp_endpoint_headers'] = {'authorization': 'Bearer token'}
        obs = _observability(config)
        assert obs['observability_backend'] == 'otlp_endpoint'
        assert obs['otlp_endpoint'] == 'https://otel.example.com/v1/traces'
        assert obs['otlp_headers'] == {'authorization': 'Bearer token'}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
