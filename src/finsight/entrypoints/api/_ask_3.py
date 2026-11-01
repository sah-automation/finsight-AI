"""Call helpers for the ask use case."""

from __future__ import annotations

import inspect
from typing import Any


async def _call_stream(
    use_case: Any, data: dict[str, Any], context: Any, frozen_context: Any = None
) -> Any:
    stream_method = getattr(use_case, 'stream', None)
    if not callable(stream_method):
        return None
    question = data.get('question')
    ctx = frozen_context if frozen_context is not None else context
    try:
        result = stream_method(ctx, question)
        if inspect.isawaitable(result):
            result = await result
    except TypeError:
        try:
            result = stream_method(request_context=ctx, question=question)
            if inspect.isawaitable(result):
                result = await result
        except TypeError:
            return None
    return result


async def _invoke(use_case: Any, context: Any, question: Any) -> Any:
    run_method = getattr(use_case, 'run', None)
    if not callable(run_method):
        raise RuntimeError('ask use case is not callable')  # noqa: TRY004
    result = run_method(context, question)
    if inspect.isawaitable(result):
        result = await result
    return result


__all__ = ['_call_stream', '_invoke']
