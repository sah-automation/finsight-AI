# ruff: noqa: BLE001, PLR0912, PLR0913, PLR0917, PLR2004, TRY300, S110, RUF059, PLC0415
"""LLM gateway streaming helpers."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any

from ._llm_gateway_gemini import (
    _apply_gemini_3_sampling_guidance,
    _is_gemini_3,
    _without_deprecated_sampling,
)
from ._llm_gateway_messages import _extract_text
from ._llm_gateway_usage import _alert_fallback_3, _record_usage

_LOGGER = logging.getLogger(__name__)


def _build_provider_call(
    self: Any,
    model: dict[str, Any],
    messages: list[dict[str, Any]],
    params: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the provider call kwargs and the effective caller parameters.

    Gemini 3+ deprecates ``temperature``/``top_p``/``top_k`` (issue #262): the
    gateway keeps them out of the provider call and folds determinism guidance
    into the system instructions instead. Other model families are untouched.
    """
    kwargs: dict[str, Any] = {
        'model': model.get('model_id') or model.get('model'),
        'messages': messages,
        'stream': True,
        'max_tokens': model.get('max_tokens'),
        'temperature': model.get('temperature'),
        'timeout': timeout,
    }
    provider_params = params
    if _is_gemini_3(kwargs['model']):
        kwargs.pop('temperature', None)
        kwargs['messages'] = _apply_gemini_3_sampling_guidance(messages)
        provider_params = _without_deprecated_sampling(params)
    return kwargs, provider_params


async def _open_stream(
    self: Any, model: dict[str, Any], messages: list[dict[str, Any]], params: dict[str, Any]
) -> tuple[dict[str, Any], Any, Any, Exception | None]:
    retries = int(model.get('max_retries', 0) or 0)
    delay = float(model.get('retry_base_delay_seconds', 1.0) or 0.0)
    timeout = float(model.get('timeout_seconds', self.timeout) or self.timeout)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            fn = self.completion_func
            if not callable(fn):
                import finsight.adapters.llm.lite_llm_gateway as _main

                resolver = getattr(_main, '_resolve_acompletion', None)
                if callable(resolver):
                    fn = resolver()
            kwargs, provider_params = _build_provider_call(self, model, messages, params, timeout)
            if self.prompt_cache_enabled:
                kwargs.setdefault('stream_options', {'include_usage': True})
            result = (
                fn(**kwargs)
                if not provider_params
                else fn(
                    **{**kwargs, **{k: v for k, v in provider_params.items() if k not in kwargs}}
                )
            )
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, (list, tuple)):

                async def _from_list(items: list[Any]) -> Any:
                    for item in items:
                        yield item

                stream = _from_list(list(result))
            elif hasattr(result, '__aiter__') or hasattr(result, '__anext__'):
                stream = result
            else:

                async def _single(value: Any) -> Any:
                    yield value

                stream = _single(result)
            first = await asyncio.wait_for(stream.__anext__(), timeout=self.first_token_timeout)
            return model, stream, first, None
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(delay)
    return (
        model,
        None,
        None,
        (last_error if last_error is not None else RuntimeError('unknown error')),
    )


async def _attempt_step(
    self: Any,
    primary_model: dict[str, Any],
    backup_model: dict[str, Any] | None,
    messages: list[dict[str, Any]],
    params: dict[str, Any],
) -> tuple[dict[str, Any], Any, Any] | None:
    loop_start = time.monotonic()
    primary_task = asyncio.create_task(_open_stream(self, primary_model, messages, params))
    backup_task: asyncio.Task[Any] | None = None
    if backup_model is not None and self.backup_enabled:

        async def delayed_backup() -> Any:
            await asyncio.sleep(self.backup_delay)
            return await _open_stream(self, backup_model, messages, params)

        backup_task = asyncio.create_task(delayed_backup())
    tasks: dict[asyncio.Task[Any], tuple[str, dict[str, Any]]] = {
        primary_task: ('primary', primary_model)
    }
    if backup_task is not None:
        tasks[backup_task] = ('backup', backup_model)  # type: ignore[assignment]
    winner_model: dict[str, Any] | None = None
    winner_stream: Any = None
    winner_first: Any = None
    while tasks:
        remaining = self.first_token_timeout - (time.monotonic() - loop_start)
        if remaining <= 0:
            for task in list(tasks):
                task.cancel()
            break
        done, pending = await asyncio.wait(
            set(tasks), timeout=remaining, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            for task in list(tasks):
                task.cancel()
            break
        for task in done:
            label, model = tasks.pop(task)
            try:
                _, stream, first, error = task.result()
            except asyncio.CancelledError:
                error = RuntimeError('cancelled')
                stream = None
                first = None
            except Exception as exc:
                error = exc
                stream = None
                first = None
            if error is None and stream is not None:
                winner_model = model
                winner_stream = stream
                winner_first = first
                for other in list(tasks):
                    other.cancel()
                tasks.clear()
                break
        if winner_model is not None:
            break
    for task in list(tasks):
        task.cancel()
    if winner_model is not None and winner_stream is not None:
        return winner_model, winner_stream, winner_first
    return None


def _to_chunk(chunk: Any, model_id: str, stream_chunk_cls: Any) -> Any:
    return stream_chunk_cls(_extract_text(chunk), model=model_id, model_name=model_id, raw=chunk)


async def _stream_chain(
    self: Any,
    chain: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    params: dict[str, Any],
    company_id: Any,
    trace_id: Any,
    stream_chunk_cls: Any,
) -> Any:
    for _index, primary_model in enumerate(chain):
        backup_model = chain[1] if (len(chain) > 1 and primary_model is chain[0]) else None
        if backup_model is primary_model:
            backup_model = None
        result = await _attempt_step(self, primary_model, backup_model, messages, params)
        if result is None:
            continue
        chosen_model, rest_stream, first_chunk = result
        model_id = str(chosen_model.get('model_id') or chosen_model.get('model'))
        if len(chain) >= 3 and model_id == str(chain[-1].get('model_id') or chain[-1].get('model')):
            _alert_fallback_3(self, model_id, company_id)
        await _record_usage(self, model_id, company_id, trace_id=trace_id, units=1)
        yield _to_chunk(first_chunk, model_id, stream_chunk_cls)
        try:
            async for chunk in rest_stream:
                yield _to_chunk(chunk, model_id, stream_chunk_cls)
        except Exception:
            pass
        return
    unavailable = 'We are temporarily unavailable. Please try again.'
    yield stream_chunk_cls(unavailable, model='unavailable', model_name='unavailable', type='error')
