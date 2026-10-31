"""Switch test for parallel_steps."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from finsight.application.ask_question.ask_question import AskQuestionUseCase
from finsight.core.config.models import SwitchesConfig


@dataclass
class _TestConfig:
    switches: SwitchesConfig


@pytest.mark.switch
class TestParallelStepsSwitch:
    """Tests for parallel_steps switch."""

    @pytest.mark.switch
    def test_parallel_steps_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        config = _TestConfig(switches=SwitchesConfig(parallel_steps=True))
        use_case = AskQuestionUseCase(config=config)
        assert use_case.parallel_steps is True

    @pytest.mark.switch
    def test_parallel_steps_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        config = _TestConfig(switches=SwitchesConfig(parallel_steps=False))
        use_case = AskQuestionUseCase(config=config)
        assert use_case.parallel_steps is False
