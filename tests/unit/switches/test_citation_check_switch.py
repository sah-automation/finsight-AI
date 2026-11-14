"""Switch test for per_sentence_citation_check."""

from __future__ import annotations

import pytest

from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestCitationCheckSwitch:
    """Tests for per_sentence_citation_check switch."""

    @pytest.mark.switch
    def test_citation_check_on(self) -> None:
        """Test behavior when switch is ENABLED (per_sentence mode)."""
        switches = SwitchesConfig(per_sentence_citation_check=True)
        # The switch is used to determine the mode in config
        assert switches.per_sentence_citation_check is True

    @pytest.mark.switch
    def test_citation_check_off(self) -> None:
        """Test behavior when switch is DISABLED (full_answer mode)."""
        switches = SwitchesConfig(per_sentence_citation_check=False)
        assert switches.per_sentence_citation_check is False
