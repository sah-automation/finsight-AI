# Switch test for textract_enabled

from __future__ import annotations

import pytest


@pytest.mark.switch
class TestutextractSwitch:
    """Tests for textract_enabled switch."""

    @pytest.mark.switch
    def test_textract_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        pytest.skip('Not yet implemented')

    @pytest.mark.switch
    def test_textract_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        pytest.skip('Not yet implemented')
