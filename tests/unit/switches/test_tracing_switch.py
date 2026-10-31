"""Switch test for detailed_tracing_enabled."""

from __future__ import annotations

import pytest

from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestTracingSwitch:
    """Tests for detailed_tracing_enabled switch."""

    @pytest.mark.switch
    def test_tracing_on(self) -> None:
        """Test behavior when switch is ENABLED."""
        switches = SwitchesConfig(detailed_tracing_enabled=True)
        adapter = TracingAdapter(config={'switches': switches})
        assert adapter.detailed_tracing_enabled is True

    @pytest.mark.switch
    def test_tracing_off(self) -> None:
        """Test behavior when switch is DISABLED."""
        switches = SwitchesConfig(detailed_tracing_enabled=False)
        adapter = TracingAdapter(config={'switches': switches})
        assert adapter.detailed_tracing_enabled is False
