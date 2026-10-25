# Switch test for reranker_enabled

from __future__ import annotations

import pytest


@pytest.mark.switch
class TestRerankerSwitch:
    """Tests for reranker_enabled switch."""

    @pytest.mark.switch
    def test_reranker_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        pytest.skip('Not yet implemented')

    @pytest.mark.switch
    def test_reranker_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        pytest.skip('Not yet implemented')
