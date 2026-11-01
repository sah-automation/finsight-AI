"""Switch test for parallel_steps."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from finsight.application.ask_question.ask_question import AskQuestion
from finsight.core.config.models import SwitchesConfig


@dataclass
class _TestConfig:
    switches: SwitchesConfig


@pytest.mark.switch
class _Null:
    pass


class TestParallelStepsSwitch:
    """Tests for parallel_steps switch."""

    @pytest.mark.switch
    def test_parallel_steps_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        config = _TestConfig(switches=SwitchesConfig(parallel_steps=True))
        use_case = AskQuestion(
            config=config,
            llm_gateway=_Null(),
            embedding_provider=_Null(),
            hybrid_search=_Null(),
            reranker=_Null(),
            metric_repository=_Null(),
            answer_cache=_Null(),
            waiting_line=_Null(),
            tracing=_Null(),
            signing_key='secret-key-1234567890',
        )
        assert use_case.parallel_steps is True

    @pytest.mark.switch
    def test_parallel_steps_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        config = _TestConfig(switches=SwitchesConfig(parallel_steps=False))
        use_case = AskQuestion(
            config=config,
            llm_gateway=_Null(),
            embedding_provider=_Null(),
            hybrid_search=_Null(),
            reranker=_Null(),
            metric_repository=_Null(),
            answer_cache=_Null(),
            waiting_line=_Null(),
            tracing=_Null(),
            signing_key='secret-key-1234567890',
        )
        assert use_case.parallel_steps is False
