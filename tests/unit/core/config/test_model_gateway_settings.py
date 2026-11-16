"""Tests for the model-gateway settings seam.

Adapters and entrypoints never read ``os.environ``; the single configuration
layer exposes the gateway transport settings as plain values (the same pattern
as ``aws_settings`` for boto3 client kwargs).
"""

from __future__ import annotations

import pytest

from finsight.core.config import model_gateway_settings as module


@pytest.mark.unit
class TestModelGatewaySettings:
    """Caller-side transport settings (API function)."""

    def test_reads_url_token_and_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MODEL_GATEWAY_URL', 'https://gw.lambda-url.us-east-1.on.aws')
        monkeypatch.setenv('MODEL_GATEWAY_AUTH_TOKEN', 'master-key')
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        settings = module.model_gateway_settings()

        assert settings['base_url'] == 'https://gw.lambda-url.us-east-1.on.aws'
        assert settings['auth_token'] == 'master-key'
        assert settings['region'] == 'us-east-1'

    def test_absent_variables_yield_empty_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('MODEL_GATEWAY_URL', raising=False)
        monkeypatch.delenv('MODEL_GATEWAY_AUTH_TOKEN', raising=False)
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)

        assert module.model_gateway_settings() == {}

    def test_auth_token_is_optional(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MODEL_GATEWAY_URL', 'https://gw.lambda-url.us-east-1.on.aws')
        monkeypatch.delenv('MODEL_GATEWAY_AUTH_TOKEN', raising=False)
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)

        settings = module.model_gateway_settings()

        assert settings == {'base_url': 'https://gw.lambda-url.us-east-1.on.aws'}


@pytest.mark.unit
class TestGatewayRuntimeSettings:
    """Gateway-side runtime settings (the gateway function itself)."""

    def test_reads_master_key_param_and_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            'MODEL_GATEWAY_MASTER_KEY_PARAM', '/finsight/prod/model_gateway_master_key'
        )
        monkeypatch.setenv('AWS_REGION', 'us-west-2')

        settings = module.gateway_runtime_settings()

        assert settings['master_key_param'] == '/finsight/prod/model_gateway_master_key'
        assert settings['region'] == 'us-west-2'

    def test_absent_master_key_param_yields_empty_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv('MODEL_GATEWAY_MASTER_KEY_PARAM', raising=False)
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)

        assert module.gateway_runtime_settings() == {}

    def test_region_defaults_to_us_east_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            'MODEL_GATEWAY_MASTER_KEY_PARAM', '/finsight/prod/model_gateway_master_key'
        )
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)

        settings = module.gateway_runtime_settings()

        assert settings['region'] == 'us-east-1'
