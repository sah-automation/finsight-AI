"""Switch test for ocr_fallback_enabled."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestOcrFallbackSwitch:
    """Tests for ocr_fallback_enabled switch."""

    @pytest.mark.switch
    def test_ocr_fallback_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(ocr_fallback_enabled=True)
        assert switches.ocr_fallback_enabled is True

    @pytest.mark.switch
    def test_ocr_fallback_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(ocr_fallback_enabled=False)
        assert switches.ocr_fallback_enabled is False
