"""Switch test for llm_content_capture_enabled."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestLlmContentCaptureSwitch:
    """Tests for llm_content_capture_enabled switch."""

    @pytest.mark.switch
    def test_llm_content_capture_on(self) -> None:
        switches = SwitchesConfig(llm_content_capture_enabled=True)
        assert switches.llm_content_capture_enabled is True

    @pytest.mark.switch
    def test_llm_content_capture_off(self) -> None:
        switches = SwitchesConfig(llm_content_capture_enabled=False)
        assert switches.llm_content_capture_enabled is False
