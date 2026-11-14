"""Switch test for parallel_retrieval_enabled."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestParallelRetrievalSwitch:
    """Tests for parallel_retrieval_enabled switch."""

    @pytest.mark.switch
    def test_parallel_retrieval_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(parallel_retrieval_enabled=True)
        assert switches.parallel_retrieval_enabled is True

    @pytest.mark.switch
    def test_parallel_retrieval_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(parallel_retrieval_enabled=False)
        assert switches.parallel_retrieval_enabled is False
