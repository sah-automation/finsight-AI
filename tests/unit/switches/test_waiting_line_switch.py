"""Switch test for waiting_line_enabled."""

from __future__ import annotations

import pytest

from finsight.composition import build_waiting_line
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestWaitingLineSwitch:
    @pytest.mark.switch
    def test_waiting_line_on(self) -> None:
        switches = SwitchesConfig(waiting_line_enabled=True)
        wl = build_waiting_line(config={'switches': switches})
        assert wl is not None

    @pytest.mark.switch
    def test_waiting_line_off(self) -> None:
        switches = SwitchesConfig(waiting_line_enabled=False)
        wl = build_waiting_line(config={'switches': switches})
        assert wl is not None
