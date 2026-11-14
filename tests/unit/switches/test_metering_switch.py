"""Switch test for usage_metering_enabled."""

from __future__ import annotations

import pytest

from finsight.adapters.metering.dynamo_metering import DynamoMetering
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestMeteringSwitch:
    """Tests for usage_metering_enabled switch."""

    @pytest.mark.switch
    def test_metering_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(usage_metering_enabled=True)
        metering = DynamoMetering(config={'switches': switches})
        assert metering.metering_enabled is True

    @pytest.mark.switch
    def test_metering_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(usage_metering_enabled=False)
        metering = DynamoMetering(config={'switches': switches})
        assert metering.metering_enabled is False
