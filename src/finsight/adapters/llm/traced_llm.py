# ruff: noqa: PLR0911, BLE001, PLR0912, PLR0915
"""Traced LLM decorator (outermost in the decorator stack)."""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Mapping
from typing import Any

from .lite_llm_gateway import LiteLLMGateway

_LOGGER = logging.getLogger(__name__)


def _resolve_wrapped(kwargs: dict[str, Any], args: tuple[Any, ...]) -> tuple[Any, tuple[Any, ...]]:
    wrapped = (
        kwargs.pop('wrapped', None)
        or kwargs.pop('gateway', None)
        or kwargs.pop('llm', None)
        or kwargs.pop('target', None)
        or kwargs.pop('inner', None)
    )
    if wrapped is None and args and not hasattr(args[0], 'config'):
        wrapped = args[0]
        args = args[1:]
    return wrapped, args


def _tracer_from(kwargs: dict[str, Any], config: Any = None, container: Any = None) -> Any:
    tracing = kwargs.pop('tracing', None)
    if tracing is None:
        tracing = kwargs.pop('tracer', None)
    if tracing is None:
        tracing = kwargs.pop('tracing_port', None)
    if tracing is None:
        tracing = kwargs.pop('span_tracer', None)
    if tracing is None:
        tracing = kwargs.pop('span_tracing', None)
    if tracing is None and container is not None:
        tracing = getattr(container, 'tracing', None)
    return tracing


class TracedLLM(LiteLLMGateway):
    """Decorator that emits tracing spans around an inner LLM gateway."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.wrapped = (
            kwargs.get('wrapped')
            or kwargs.get('gateway')
            or kwargs.get('llm')
            or kwargs.get('target')
            or kwargs.get('inner')
        )
        args_list = list(args)
        if self.wrapped is None and args_list:
            self.wrapped = args_list.pop(0)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'gateway', 'llm', 'target', 'inner'):
            kwargs.pop(key, None)
        self.tracing = _tracer_from(kwargs, kwargs.get('config'), kwargs.get('container'))
        self.operation = str(kwargs.pop('operation', kwargs.pop('span_name', 'model_generation')))
        self._inner = self.wrapped
        self._traced_operation = self.operation
        if self._inner is None:
            super().__init__(*args_list, **kwargs)

    async def _trace(self, company_id: Any) -> None:
        tracer = self.tracing
        if tracer is None:
            return
        try:
            method = None
            for name in (
                'start_span',
                'span',
                'emit_span',
                'trace',
                'trace_operation',
                'record_span',
                'emit',
                'record',
            ):
                candidate = getattr(tracer, name, None)
                if callable(candidate):
                    method = candidate
                    break
            if method is None:
                return
            attributes = _standard_attributes(self, company_id)
            try:
                sig = inspect.signature(method)
                accepts = 'attributes' in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                )
            except (TypeError, ValueError):
                accepts = True
            if accepts:
                try:
                    result = method(company_id, self.operation, attributes=attributes)
                except TypeError:
                    result = method(company_id, self.operation)
            else:
                result = method(company_id, self.operation)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            _LOGGER.debug('tracer call failed: %s', exc)
            return

    async def _emit_span(
        self,
        company_id: Any,
        started: float,
        result: Any = None,
        first_token_latency_ms: float | None = None,
        request: Any = None,
    ) -> None:
        tracer = self.tracing
        if tracer is None:
            return
        try:
            method = None
            for name in (
                'start_span',
                'span',
                'emit_span',
                'trace',
                'trace_operation',
                'record_span',
                'emit',
                'record',
            ):
                candidate = getattr(tracer, name, None)
                if callable(candidate):
                    method = candidate
                    break
            if method is None:
                return
            duration_ms = (time.perf_counter() - started) * 1000.0
            attributes = _standard_attributes(self, company_id)
            attributes['duration'] = duration_ms
            attributes['duration_ms'] = duration_ms
            if first_token_latency_ms is not None:
                attributes['first_token_latency_ms'] = first_token_latency_ms

            inner = getattr(self, '_inner', None)
            retry_count = 0
            for candidate in (inner, getattr(inner, '_inner', None)):
                if candidate is None:
                    continue
                for attr in ('retry_count', 'retries'):
                    value = getattr(candidate, attr, None)
                    if isinstance(value, int):
                        retry_count = max(retry_count, value)
            attributes.setdefault('retry_count', retry_count)
            attributes.setdefault('retries', retry_count)

            cache_hit = False
            for candidate in (inner, getattr(inner, '_inner', None), result):
                if candidate is None:
                    continue
                value = getattr(candidate, 'cache_hit', None)
                if isinstance(value, bool):
                    cache_hit = cache_hit or value
                if isinstance(candidate, dict):
                    value = candidate.get('cache_hit')
                    if isinstance(value, bool):
                        cache_hit = cache_hit or value
            attributes['cache_hit'] = cache_hit

            tokens_prompt = 0
            tokens_completion = 0
            tokens_total = 0
            for source in (result, inner, getattr(inner, '_inner', None)):
                if source is None:
                    continue
                for prompt_key in ('tokens_prompt', 'prompt_tokens', 'input_tokens'):
                    value = getattr(source, prompt_key, None)
                    if value is None and isinstance(source, dict):
                        value = source.get(prompt_key)
                    if isinstance(value, int):
                        tokens_prompt = max(tokens_prompt, value)
                for completion_key in ('tokens_completion', 'completion_tokens', 'output_tokens'):
                    value = getattr(source, completion_key, None)
                    if value is None and isinstance(source, dict):
                        value = source.get(completion_key)
                    if isinstance(value, int):
                        tokens_completion = max(tokens_completion, value)
                for total_key in ('tokens_total', 'total_tokens'):
                    value = getattr(source, total_key, None)
                    if value is None and isinstance(source, dict):
                        value = source.get(total_key)
                    if isinstance(value, int):
                        tokens_total = max(tokens_total, value)
            if tokens_total == 0:
                tokens_total = tokens_prompt + tokens_completion
            attributes['tokens_prompt'] = tokens_prompt
            attributes['tokens_completion'] = tokens_completion
            attributes['tokens_total'] = tokens_total
            attributes['prompt_tokens'] = tokens_prompt
            attributes['completion_tokens'] = tokens_completion
            attributes['total_tokens'] = tokens_total

            fallback_tags: list[Any] = []
            fallback_3_used = False
            fallback_model_used = None
            for source in (inner, getattr(inner, '_inner', None)):
                if source is None:
                    continue
                tags = getattr(source, '_tags', None)
                if isinstance(tags, list):
                    fallback_tags = tags
                fallback_3_used = fallback_3_used or bool(getattr(source, 'fallback_3_used', False))
                trace = getattr(source, '_last_trace', None)
                if isinstance(trace, dict):
                    fallback_3_used = fallback_3_used or bool(trace.get('fallback_3_used'))
                    fallback_model_used = fallback_model_used or trace.get('fallback_3_model')
            if isinstance(result, dict):
                trace = result.get('trace')
                if isinstance(trace, dict):
                    fallback_tags = fallback_tags or trace.get('fallback_tags', [])
                    fallback_3_used = fallback_3_used or bool(trace.get('fallback_3_used'))
            attributes['fallback_tags'] = fallback_tags
            attributes['fallback_3_used'] = fallback_3_used
            if fallback_model_used is not None:
                attributes['fallback_model_used'] = fallback_model_used

            queue_wait = 0
            for source in (inner, getattr(inner, '_inner', None)):
                if source is None:
                    continue
                for attr in ('queue_wait', 'queue_wait_ms'):
                    value = getattr(source, attr, None)
                    if isinstance(value, (int, float)):
                        queue_wait = max(queue_wait, int(value))
            attributes['queue_wait'] = queue_wait
            attributes['queue_wait_ms'] = queue_wait

            estimated_cost = None
            for source in (inner, getattr(inner, '_inner', None)):
                if source is None:
                    continue
                rows = getattr(source, 'usage_rows', None)
                if isinstance(rows, list) and rows:
                    last_row = rows[-1]
                    if isinstance(last_row, dict):
                        estimated_cost = last_row.get('estimated_cost', last_row.get('cost'))
            attributes['estimated_cost'] = estimated_cost
            attributes['estimated_cost_usd'] = estimated_cost
            attributes['cost'] = estimated_cost

            # Full content capture (gated behind llm_content_capture_enabled).
            if _content_capture_enabled(self):
                try:
                    req_messages = _extract_request_messages(request)
                    if req_messages is not None:
                        attributes['genai.request.messages'] = req_messages
                    resp_text = _extract_response_text(result)
                    if resp_text is not None:
                        attributes['genai.response.messages'] = [
                            {'role': 'assistant', 'content': resp_text}
                        ]
                except Exception as exc:
                    _LOGGER.debug('content capture failed: %s', exc)

            try:
                sig = inspect.signature(method)
                accepts = 'attributes' in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                )
            except (TypeError, ValueError):
                accepts = True
            if accepts:
                try:
                    result_span = method(company_id, self.operation, attributes=attributes)
                except TypeError:
                    result_span = method(company_id, self.operation)
            else:
                result_span = method(company_id, self.operation)
            if inspect.isawaitable(result_span):
                await result_span
        except Exception as exc:
            _LOGGER.debug('span emission failed: %s', exc)
            return

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        cid = company_id if company_id is not None else kwargs.get('company_id')
        target = self._inner if self._inner is not None else self
        started = time.perf_counter()
        result = None
        try:
            result = await target.complete(company_id, *args, **kwargs)
            return result
        finally:
            await self._emit_span(cid, started, result=result, request=(args, dict(kwargs)))

    async def stream(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        cid = company_id if company_id is not None else kwargs.get('company_id')
        target = self._inner if self._inner is not None else self
        started = time.perf_counter()
        first_token_at: float | None = None
        last_item: Any = None
        try:
            async for item in target.stream(company_id, *args, **kwargs):
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                last_item = item
                yield item
        finally:
            first_token_latency_ms = None
            if first_token_at is not None:
                first_token_latency_ms = (first_token_at - started) * 1000.0
            await self._emit_span(
                cid,
                started,
                result=last_item,
                first_token_latency_ms=first_token_latency_ms,
                request=(args, dict(kwargs)),
            )

    async def generate(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def chat(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        try:
            target = object.__getattribute__(self, '_inner')
        except AttributeError:
            raise AttributeError(name) from None
        if target is None or target is self:
            raise AttributeError(name)
        return getattr(target, name)


def _active_switch_values(switches_or_config: Any) -> dict[str, Any]:
    # Local copy to avoid cross-adapter imports (import-linter).
    switches = getattr(switches_or_config, 'switches', None)
    if switches is None and isinstance(switches_or_config, dict):
        switches = switches_or_config.get('switches')
    if switches is None and hasattr(switches_or_config, 'config'):
        cfg = switches_or_config.config
        switches = getattr(cfg, 'switches', None) if hasattr(cfg, 'switches') else cfg
    if isinstance(switches, dict):
        try:
            return {str(k): v for k, v in switches.items()}
        except Exception:
            return {}
    if switches is None:
        switches = switches_or_config
    if isinstance(switches, dict):
        try:
            return {str(k): v for k, v in switches.items()}
        except Exception:
            return {}
    result: dict[str, Any] = {}
    try:
        _model_fields = (
            getattr(type(switches), 'model_fields', None)
            or getattr(switches, 'model_fields', None)
            or {}
        )
        for field in _model_fields:
            result[str(field)] = getattr(switches, field, None)
    except Exception:  # noqa: S110
        pass
    return result


def _standard_attributes(obj: Any, company_id: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {'step': getattr(obj, 'operation', None)}
    inner = getattr(obj, '_inner', None)
    model = None
    _seen: set[int] = set()
    _cur = inner
    while _cur is not None and id(_cur) not in _seen:
        _seen.add(id(_cur))
        _mid = getattr(_cur, 'model_id', None)
        if _mid not in (None, 'default', 'default-embedding', 'default-llm'):
            model = _mid
            break
        _m = getattr(_cur, 'model', None)
        if _m not in (None,):
            model = _m
            break
        _cur = getattr(_cur, '_inner', None) or getattr(_cur, 'wrapped', None)
    if model is None:
        model = getattr(obj, 'model', None)

    if model is not None:
        attrs['model_name'] = model
        attrs['model'] = model
    # active switch values (best effort)
    switches = _find_config(obj)
    try:
        vals = _active_switch_values(switches if switches is not None else obj)
        if vals:
            attrs['active_switch_values'] = vals
            attrs['active_switches'] = vals
            attrs['switches'] = vals
    except Exception:  # noqa: S110
        pass
    attrs.setdefault('retry_count', 0)
    attrs.setdefault('retries', 0)
    attrs.setdefault('cache_hit', False)
    attrs.setdefault('queue_wait', 0)
    attrs.setdefault('queue_wait_ms', 0)
    attrs.setdefault('duration', 0)
    attrs.setdefault('duration_ms', 0)
    return {
        k: v
        for k, v in attrs.items()
        if v is not None or k in ('cache_hit', 'retry_count', 'queue_wait', 'duration')
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'true', 'yes', '1', 'on', 'enabled'}
    if value is None:
        return False
    try:
        return bool(value)
    except Exception:
        return False


def _find_config(obj: Any) -> Any:
    seen: set[int] = set()
    cur: Any = obj
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        cfg = getattr(cur, 'config', None)
        if cfg is not None:
            return cfg
        cur = (
            getattr(cur, '_inner', None)
            or getattr(cur, 'wrapped', None)
            or getattr(cur, '_wrapped', None)
        )
    tracer = getattr(obj, 'tracing', None)
    if tracer is not None and tracer is not obj:
        return _find_config(tracer)
    return None


def _content_capture_enabled(obj: Any) -> bool:
    cfg = _find_config(obj)
    if cfg is None:
        return False
    switches = getattr(cfg, 'switches', None)
    if switches is None and isinstance(cfg, dict):
        switches = cfg.get('switches')
    if switches is None:
        switches = cfg
    if isinstance(switches, dict):
        return _truthy(switches.get('llm_content_capture_enabled', False))
    return _truthy(getattr(switches, 'llm_content_capture_enabled', False))


def _extract_request_messages(request: Any) -> list[dict[str, Any]] | None:
    if not request:
        return None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = {}
    if isinstance(request, tuple) and len(request) == 2:  # noqa: PLR2004
        args, kwargs = request[0], request[1] if isinstance(request[1], dict) else {}
    elif isinstance(request, dict):
        kwargs = request
    if not isinstance(kwargs, dict):
        kwargs = {}
    messages = kwargs.get('messages')
    if isinstance(messages, list) and messages:
        return [dict(m) if isinstance(m, Mapping) else {'content': m} for m in messages]
    prompt = kwargs.get('prompt')
    if prompt is None:
        prompt = kwargs.get('question')
    if prompt is None and args:
        first = args[0] if args else None
        if isinstance(first, str):
            prompt = first
        elif isinstance(first, list):
            messages = first
            if messages:
                return [dict(m) if isinstance(m, Mapping) else {'content': m} for m in messages]
    if prompt is None:
        return None
    return [{'role': 'user', 'content': prompt}]


def _extract_response_text(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        for key in ('content', 'text', 'answer', 'response'):
            value = result.get(key)
            if isinstance(value, str):
                return value
        for key in ('delta', 'message'):
            value = result.get(key)
            if isinstance(value, Mapping):
                text = _extract_response_text(value)
                if text:
                    return text
        choices = result.get('choices')
        if isinstance(choices, list) and choices:
            return _extract_response_text(choices[0])
    if isinstance(result, (list, tuple)):
        pieces: list[str] = []
        for item in result:
            text = _extract_response_text(item)
            if text:
                pieces.append(text)
        if pieces:
            return ''.join(pieces)
    content = getattr(result, 'content', None)
    if isinstance(content, str):
        return content
    text = getattr(result, 'text', None)
    if isinstance(text, str):
        return text
    try:
        return str(result)
    except Exception:
        return None


__all__ = ['TracedLLM']
