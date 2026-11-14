"""Switch test for prompt_cache_enabled."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestPromptCacheSwitch:
    """Tests for prompt_cache_enabled switch."""

    @pytest.mark.switch
    def test_prompt_cache_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(prompt_cache_enabled=True)
        assert switches.prompt_cache_enabled is True

    @pytest.mark.switch
    def test_prompt_cache_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(prompt_cache_enabled=False)
        assert switches.prompt_cache_enabled is False
