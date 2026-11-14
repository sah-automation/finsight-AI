# ruff: noqa: BLE001, PLR0912, PLR0913, PLR0917, PLR2004, TRY300, RUF059, PLC0415
"""LLM gateway streaming helpers."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import time
from collections.abc import Mapping
from typing import Any

from finsight.core.logging import get_trace_id

from ._llm_gateway_gemini import (
    _apply_gemini_3_sampling_guidance,
    _is_gemini_3,
    _without_deprecated_sampling,
)
from ._llm_gateway_messages import _extract_text
from ._llm_gateway_usage import _alert_fallback_3, _record_usage

_LOGGER = logging.getLogger(__name__)


def _build_provider_call(
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
        self.last_retry_count = attempt
        try:
            fn = self.completion_func
            if not callable(fn):
                from finsight.adapters.llm.lite_llm_gateway import _resolve_acompletion as _resolver

                fn = _resolver()
            kwargs, provider_params = _build_provider_call(model, messages, params, timeout)
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
            _LOGGER.warning(
                '[llm] per-model call failed for %s',
                str(model.get('model_id') or model.get('model')),
                exc_info=exc,
                extra={'trace_id': get_trace_id()},
            )
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


def _extract_usage(chunk: Any) -> dict[str, Any]:
    """Extract a usage dict from a provider chunk (dict or object)."""
    if chunk is None:
        return {}
    usage = None
    if isinstance(chunk, Mapping):
        for key in ('usage', 'token_usage', 'usage_metadata'):
            if chunk.get(key) is not None:
                usage = chunk.get(key)
                break
        if usage is None and any(
            chunk.get(k) is not None for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')
        ):
            usage = chunk
    else:
        for attr in ('usage', 'token_usage', 'usage_metadata'):
            val = getattr(chunk, attr, None)
            if val is not None:
                usage = val
                break
        if usage is None and any(
            getattr(chunk, k, None) is not None
            for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')
        ):
            usage = chunk
    if usage is None:
        return {}
    if isinstance(usage, Mapping):
        return {str(k): v for k, v in usage.items()}
    result: dict[str, Any] = {}
    for attr in (
        'prompt_tokens',
        'input_tokens',
        'completion_tokens',
        'output_tokens',
        'total_tokens',
    ):
        val = getattr(usage, attr, None)
        if val is not None:
            result[attr] = val
    return result


def _usage_total(usage: dict[str, Any]) -> int:
    for key in ('total_tokens', 'tokens_total', 'total'):
        if usage.get(key) is not None:
            try:
                return int(usage[key])
            except (TypeError, ValueError):
                pass
    prompt = 0
    completion = 0
    for key in ('prompt_tokens', 'input_tokens', 'tokens_prompt'):
        if usage.get(key) is not None:
            with contextlib.suppress(TypeError, ValueError):
                prompt = max(prompt, int(usage[key]))
    for key in ('completion_tokens', 'output_tokens', 'tokens_completion'):
        if usage.get(key) is not None:
            with contextlib.suppress(TypeError, ValueError):
                completion = max(completion, int(usage[key]))
    return prompt + completion


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
        usage_acc: dict[str, Any] = {}
        try:
            usage_acc.update(_extract_usage(first_chunk))
            first_text = _extract_text(first_chunk)
            if first_text:
                yield _to_chunk(first_chunk, model_id, stream_chunk_cls)
            try:
                async for chunk in rest_stream:
                    usage_acc.update(_extract_usage(chunk))
                    text = _extract_text(chunk)
                    if text:
                        yield _to_chunk(chunk, model_id, stream_chunk_cls)
            except Exception as exc:
                _LOGGER.warning(
                    '[llm] stream failed for model %s',
                    model_id,
                    exc_info=exc,
                    extra={'trace_id': get_trace_id()},
                )
        finally:
            units = max(_usage_total(usage_acc), 1)
            await _record_usage(
                self, model_id, company_id, trace_id=trace_id, units=units, usage=usage_acc
            )
        return
    unavailable = 'We are temporarily unavailable. Please try again.'
    yield stream_chunk_cls(unavailable, model='unavailable', model_name='unavailable', type='error')
