# Switch test for metering_enabled

from __future__ import annotations

import pytest


@pytest.mark.switch
class TestumeteringSwitch:
    """Tests for metering_enabled switch."""

    @pytest.mark.switch
    def test_metering_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        pytest.skip('Not yet implemented')

    @pytest.mark.switch
    def test_metering_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        pytest.skip('Not yet implemented')
