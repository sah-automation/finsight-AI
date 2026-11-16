"""Switch test for llm_transport.

Pilot path: ``remote_gateway`` — the LLM/embedding calls go over the network to
the model-gateway Lambda (issue #330). Standard path: ``in_process`` — the
litellm chain runs inside the caller's process, exactly as before the gateway
existed. Both paths must stay written and tested (config-switch policy).
"""

from __future__ import annotations

from typing import Any

import pytest

from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.composition import build_embedding_stack, build_llm
from finsight.core.config.models import SwitchesConfig


def _unwrap_provider(stack: Any) -> Any:
    """Walk decorator wrappers (.wrapped / ._inner) down to the provider."""
    while True:
        inner = getattr(stack, 'wrapped', None) or getattr(stack, '_inner', None)
        if inner is None:
            return stack
        stack = inner


def _quiet_switches(**overrides: Any) -> SwitchesConfig:
    """Switches with metering/tracing off so the stack builds without side ports."""
    return SwitchesConfig(usage_metering_enabled=False, detailed_tracing_enabled=False, **overrides)


@pytest.mark.switch
class TestLLMTransportSwitch:
    """Tests for llm_transport switch values."""

    @pytest.mark.switch
    def test_llm_transport_remote_on(self) -> None:
        """The pilot path selects the remote model gateway."""
        switches = SwitchesConfig(llm_transport='remote_gateway')
        assert switches.llm_transport == 'remote_gateway'

    @pytest.mark.switch
    def test_llm_transport_in_process_off(self) -> None:
        """The standard path keeps litellm in process and is the default."""
        switches = SwitchesConfig()
        assert switches.llm_transport == 'in_process'
        explicit = SwitchesConfig(llm_transport='in_process')
        assert explicit.llm_transport == 'in_process'

    @pytest.mark.switch
    def test_llm_transport_invalid_off(self) -> None:
        """An unknown transport value must refuse to build a config."""
        with pytest.raises(ValueError):
            SwitchesConfig(llm_transport='pigeon_post')  # type: ignore[arg-type]


@pytest.mark.switch
class TestLLMTransportWiring:
    """The composition root wires both paths through the existing call seams."""

    @pytest.mark.switch
    def test_llm_transport_remote_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """remote_gateway injects the remote completion_func into the gateway."""
        monkeypatch.setattr(
            'finsight.core.config.model_gateway_settings.model_gateway_settings',
            lambda: {'base_url': 'https://gw.example', 'region': 'us-east-1'},
        )
        stack = build_llm(config={'switches': _quiet_switches(llm_transport='remote_gateway')})

        provider = _unwrap_provider(stack)

        assert isinstance(provider, LiteLLMGateway)
        assert provider.completion_func is not None
        assert 'remote_completion' in provider.completion_func.__qualname__

    @pytest.mark.switch
    def test_llm_transport_remote_missing_url_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """remote_gateway without MODEL_GATEWAY_URL must refuse to build."""
        monkeypatch.setattr(
            'finsight.core.config.model_gateway_settings.model_gateway_settings',
            dict,
        )
        with pytest.raises(ValueError, match='MODEL_GATEWAY_URL'):
            build_llm(config={'switches': _quiet_switches(llm_transport='remote_gateway')})

    @pytest.mark.switch
    def test_embedding_transport_remote_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """remote_gateway injects the remote embedding_func into the adapter."""
        monkeypatch.setattr(
            'finsight.core.config.model_gateway_settings.model_gateway_settings',
            lambda: {'base_url': 'https://gw.example', 'region': 'us-east-1'},
        )
        stack = build_embedding_stack(
            config={'switches': _quiet_switches(llm_transport='remote_gateway')}
        )

        provider = _unwrap_provider(stack)

        assert provider.embedding_func is not None
        assert 'remote_embedding' in provider.embedding_func.__qualname__

    @pytest.mark.switch
    def test_llm_transport_in_process_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """in_process leaves both call seams untouched (lazy litellm fallback)."""
        monkeypatch.setattr(
            'finsight.core.config.model_gateway_settings.model_gateway_settings',
            dict,
        )
        llm_stack = build_llm(config={'switches': _quiet_switches(llm_transport='in_process')})
        embedding_stack = build_embedding_stack(
            config={'switches': _quiet_switches(llm_transport='in_process')}
        )

        assert _unwrap_provider(llm_stack).completion_func is None
        assert _unwrap_provider(embedding_stack).embedding_func is None
