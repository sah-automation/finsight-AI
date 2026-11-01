"""Switch test for detailed_tracing_enabled."""

from __future__ import annotations

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.composition import build_tracing
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestTracingSwitch:
    """Tests for detailed_tracing_enabled switch."""

    @pytest.mark.switch
    def test_tracing_on(self) -> None:
        switches = SwitchesConfig(detailed_tracing_enabled=True)
        adapter = build_tracing(config={'switches': switches})
        assert isinstance(adapter, TracingAdapter)
        assert adapter.detailed_tracing_enabled is True

    @pytest.mark.switch
    def test_tracing_off(self) -> None:
        switches = SwitchesConfig(detailed_tracing_enabled=False)
        adapter = build_tracing(config={'switches': switches})
        assert isinstance(adapter, DisabledTracer)
