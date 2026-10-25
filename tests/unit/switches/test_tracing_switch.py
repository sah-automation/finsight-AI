# Switch test for tracing_enabled

from __future__ import annotations

import pytest


@pytest.mark.switch
class TestutracingSwitch:
    """Tests for tracing_enabled switch."""

    @pytest.mark.switch
    def test_tracing_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        pytest.skip('Not yet implemented')

    @pytest.mark.switch
    def test_tracing_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        pytest.skip('Not yet implemented')
