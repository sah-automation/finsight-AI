"""Tests that the ask flow is fully wired through the composition root."""

from __future__ import annotations

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.adapters.waiting_line.passthrough_waiting_line import PassthroughWaitingLine
from finsight.adapters.waiting_line.waiting_line_adapter import WaitingLineAdapter
from finsight.application.ask_question import AskQuestion
from finsight.composition import build_container, build_tracing, build_waiting_line
from finsight.core.config.loader import load_config
from finsight.core.config.models import SwitchesConfig


def test_ask_use_case_wired_with_all_ten_dependencies() -> None:
    container = build_container(config=load_config('test'))
    use_case = container.ask_question_use_case

    assert isinstance(use_case, AskQuestion)
    assert use_case._config is not None
    assert use_case._llm is not None
    assert use_case._embedding is not None
    assert use_case._search is not None
    assert use_case._reranker is not None
    assert use_case._metrics is not None
    assert use_case._cache is not None
    assert use_case._waiting is not None
    assert use_case._tracing is not None
    assert use_case._signing_key


def test_ask_wiring_selects_concrete_noop_adapters_per_switch() -> None:
    switches = SwitchesConfig(detailed_tracing_enabled=False, waiting_line_enabled=False)
    build_container(config=load_config('test'))
    # assert the builder entry points produce the no-op variants.

    tracer = build_tracing(config={'switches': switches})
    line = build_waiting_line(config={'switches': switches})
    assert isinstance(tracer, DisabledTracer)
    assert isinstance(line, PassthroughWaitingLine)

    switches_on = SwitchesConfig(detailed_tracing_enabled=True, waiting_line_enabled=True)
    assert isinstance(build_tracing(config={'switches': switches_on}), TracingAdapter)
    assert isinstance(build_waiting_line(config={'switches': switches_on}), WaitingLineAdapter)
