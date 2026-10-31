"""Switch test for async_textract_enabled."""

from __future__ import annotations

import pytest

from finsight.adapters.readers.textract_reader import TextractReader
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestTextractSwitch:
    """Tests for async_textract_enabled switch."""

    @pytest.mark.switch
    def test_textract_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(async_textract_enabled=True)
        reader = TextractReader(config={'switches': switches})
        assert reader._async_enabled() is True

    @pytest.mark.switch
    def test_textract_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(async_textract_enabled=False)
        reader = TextractReader(config={'switches': switches})
        assert reader._async_enabled() is False
