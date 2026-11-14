"""Switch test for answer_cache_enabled."""

from __future__ import annotations

import pytest

from finsight.adapters.cache.answer_cache import AnswerCache
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestAnswerCacheSwitch:
    """Tests for answer_cache_enabled switch."""

    @pytest.mark.switch
    def test_answer_cache_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(answer_cache_enabled=True)
        cache = AnswerCache(config={'switches': switches})
        assert cache.answer_cache_enabled is True

    @pytest.mark.switch
    def test_answer_cache_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(answer_cache_enabled=False)
        cache = AnswerCache(config={'switches': switches})
        assert cache.answer_cache_enabled is False
