"""Switch test for reranker_enabled."""

from __future__ import annotations

import pytest

from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestRerankerSwitch:
    """Tests for reranker_enabled switch."""

    @pytest.mark.switch
    def test_reranker_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(reranker_enabled=True)
        reranker = CohereReranker(config=switches)
        assert reranker.enabled is True

    @pytest.mark.switch
    def test_reranker_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(reranker_enabled=False)
        reranker = CohereReranker(config=switches)
        assert reranker.enabled is False
