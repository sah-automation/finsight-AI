"""Switch test for llm_transport.

Pilot path: ``remote_gateway`` — the LLM/embedding calls go over the network to
the model-gateway Lambda (issue #330). Standard path: ``in_process`` — the
litellm chain runs inside the caller's process, exactly as before the gateway
existed. Both paths must stay written and tested (config-switch policy).
"""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


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
