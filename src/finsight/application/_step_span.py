"""Shared step-span emission helper for application orchestrators.

Emits one completion span per orchestration step after the step runs, carrying
``duration_ms`` and ``outcome``. Orchestration behaviour and answers are
unchanged; this is presentation-only instrumentation.
"""

from __future__ import annotations

import inspect
import time
from typing import Any

from finsight.core.logging import get_trace_id

_TRACER_METHOD_NAMES = (
    'start_span',
    'span',
    'emit_span',
    'trace',
    'trace_operation',
    'record_span',
    'emit',
    'record',
)


def _tracer_method(tracer: Any) -> Any:
    """Return the first callable span-emission method on *tracer*, else None."""
    for name in _TRACER_METHOD_NAMES:
        candidate = getattr(tracer, name, None)
        if callable(candidate):
            return candidate
    return None


async def emit_step_span(
    tracer: Any,
    company_id: Any,
    operation: str,
    *,
    duration_ms: float,
    outcome: str,
) -> None:
    """Emit a completion span with ``duration_ms`` and ``outcome``."""
    if tracer is None:
        return
    method = _tracer_method(tracer)
    if method is None:
        return
    try:
        attributes: dict[str, Any] = {'duration_ms': duration_ms, 'outcome': outcome}
        trace_id = get_trace_id()
        if trace_id is not None:
            attributes['trace_id'] = trace_id
        res = method(company_id, operation, attributes=attributes)
        if inspect.isawaitable(res):
            await res
    except Exception:  # noqa: BLE001 - tracing is best-effort
        return


async def run_traced_step(
    tracer: Any,
    company_id: Any,
    operation: str,
    step: Any,
) -> Any:
    """Run one orchestration step and emit a completion span afterwards.

    Failed steps still produce a failure span. Returns the step's result.
    """
    if tracer is None:
        result = step()
        if inspect.isawaitable(result):
            return await result
        return result
    started = time.perf_counter()
    outcome = 'success'
    try:
        result = step()
        if inspect.isawaitable(result):
            return await result
        return result  # noqa: TRY300
    except Exception:
        outcome = 'failure'
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000.0
        await emit_step_span(
            tracer, company_id, operation, duration_ms=duration_ms, outcome=outcome
        )


__all__ = ['emit_step_span', 'run_traced_step']
