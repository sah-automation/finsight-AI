# Switch test

from __future__ import annotations

import pytest


@pytest.mark.switch
class TestSwitch:
    @pytest.mark.switch
    def test_switch_on(self) -> None:
        pytest.skip('Not yet implemented')

    @pytest.mark.switch
    def test_switch_off(self) -> None:
        pytest.skip('Not yet implemented')
