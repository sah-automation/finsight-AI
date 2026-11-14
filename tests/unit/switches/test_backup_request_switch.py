"""Switch test for backup_request_enabled."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestBackupRequestSwitch:
    """Tests for backup_request_enabled switch."""

    @pytest.mark.switch
    def test_backup_request_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(backup_request_enabled=True)
        assert switches.backup_request_enabled is True

    @pytest.mark.switch
    def test_backup_request_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(backup_request_enabled=False)
        assert switches.backup_request_enabled is False
