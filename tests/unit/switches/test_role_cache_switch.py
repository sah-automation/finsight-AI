"""Switch test for role_cache_enabled."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestRoleCacheSwitch:
    """Tests for role_cache_enabled switch."""

    @pytest.mark.switch
    def test_role_cache_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(role_cache_enabled=True)
        # Verify the switch value is correctly set
        assert switches.role_cache_enabled is True

    @pytest.mark.switch
    def test_role_cache_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(role_cache_enabled=False)
        assert switches.role_cache_enabled is False
