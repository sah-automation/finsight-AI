# ruff: noqa: PLR0912, PLR0915
from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Mapping
from typing import Any

from finsight.core.logging import get_trace_id

_LOGGER = logging.getLogger(__name__)


def _resolve_wrapped(kwargs: dict[str, Any], args: list[Any]) -> Any:
    wrapped = (
        kwargs.pop('wrapped', None)
        or kwargs.pop('reranker', None)
        or kwargs.pop('ranker', None)
        or kwargs.pop('target', None)
        or kwargs.pop('inner', None)
    )
    if wrapped is None and args:
        wrapped = args.pop(0)
    return wrapped


def _tracer_from(kwargs: dict[str, Any]) -> Any:
    for key in ('tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing'):
        if kwargs.get(key) is not None:
            return kwargs.pop(key)
    return kwargs.get('tracing') or kwargs.get('tracer')


class TracedReranker:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'reranker', 'ranker', 'target', 'inner'):
            kwargs.pop(key, None)
        self.tracing = _tracer_from(kwargs)
        self.operation = str(kwargs.pop('operation', 'rerank'))
        self._inner = wrapped
        self.wrapped = wrapped
        self._config = kwargs.get('config')
        self._kwargs = kwargs

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
                    result = method(
                        company_id, self.operation, trace_id=get_trace_id(), attributes=attributes
                    )
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

            inner = getattr(self, '_inner', None)
            actual_retry_count: int | None = None
            configured_retries = 0
            seen: set[int] = set()
            candidate = inner
            while candidate is not None and id(candidate) not in seen:
                seen.add(id(candidate))
                actual = getattr(candidate, 'last_retry_count', None)
                if isinstance(actual, int):
                    actual_retry_count = (
                        actual if actual_retry_count is None else max(actual_retry_count, actual)
                    )
                for attr in ('retry_count', 'retries'):
                    value = getattr(candidate, attr, None)
                    if isinstance(value, int):
                        configured_retries = max(configured_retries, value)
                candidate = getattr(candidate, '_inner', None) or getattr(
                    candidate, 'wrapped', None
                )
            retry_count = (
                actual_retry_count if actual_retry_count is not None else configured_retries
            )
            attributes['retry_count'] = retry_count
            attributes['retries'] = retry_count

            cache_hit = False
            for candidate in (inner, getattr(inner, '_inner', None), result):
                if candidate is None:
                    continue
                value = getattr(candidate, 'cache_hit', None)
                if isinstance(value, bool):
                    cache_hit = cache_hit or value
            attributes['cache_hit'] = cache_hit

            fallback_tags: list[Any] = []
            fallback_3_used = False
            if isinstance(getattr(result, 'trace', None), dict):
                fallback_tags = result.trace.get('fallback_tags', fallback_tags) or fallback_tags
                fallback_3_used = bool(result.trace.get('reranker_fallback', False))
            if getattr(result, 'fallback', False):
                fallback_tags = fallback_tags or ['reranker_fallback']
            attributes['fallback_tags'] = fallback_tags
            attributes['fallback_3_used'] = fallback_3_used
            attributes['rerank_fallback'] = bool(getattr(result, 'fallback', False))

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

            if _content_capture_enabled(self):
                try:
                    query, candidates = _extract_rerank_content(request)
                    if query is not None:
                        attributes['genai.rerank.query'] = query
                    if candidates is not None:
                        attributes['genai.rerank.candidates'] = candidates
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
                    result_span = method(
                        company_id, self.operation, trace_id=get_trace_id(), attributes=attributes
                    )
                except TypeError:
                    result_span = method(company_id, self.operation)
            else:
                result_span = method(company_id, self.operation)
            if inspect.isawaitable(result_span):
                await result_span
        except Exception as exc:
            _LOGGER.debug('span emission failed: %s', exc)
            return

    async def rerank(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        cid = company_id if company_id is not None else kwargs.get('company_id')
        target = self._inner if self._inner is not None else self
        started = time.perf_counter()
        result = None
        try:
            result = await target.rerank(company_id, *args, **kwargs)
            return result
        finally:
            await self._emit_span(cid, started, result=result, request=(args, dict(kwargs)))

    def __getattr__(self, name: str) -> Any:
        target = self._inner
        if target is None:
            raise AttributeError(name)
        return getattr(target, name)

    @property
    def wrapped(self) -> Any:
        return getattr(self, '_inner', None)

    @wrapped.setter
    def wrapped(self, value: Any) -> None:
        self._inner = value


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
    attrs.setdefault('rerank_fallback', False)
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


def _extract_rerank_content(request: Any) -> tuple[Any, Any]:
    if not request:
        return (None, None)
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = {}
    if isinstance(request, tuple) and len(request) == 2:  # noqa: PLR2004
        args, kwargs = request[0], request[1] if isinstance(request[1], dict) else {}
    elif isinstance(request, dict):
        kwargs = request
    if not isinstance(kwargs, dict):
        kwargs = {}
    query = kwargs.get('query')
    if query is None:
        query = kwargs.get('question')
    if query is None and args:
        for a in args:
            if isinstance(a, str):
                query = a
                break
    candidates = kwargs.get('candidates')
    if candidates is None:
        candidates = kwargs.get('documents')
    if candidates is None:
        candidates = kwargs.get('results')
    if candidates is None:
        candidates = kwargs.get('chunks')
    if candidates is None and len(args) > 1:
        for a in args[1:]:
            if isinstance(a, (list, tuple)):
                candidates = list(a)
                break
    if isinstance(candidates, tuple):
        candidates = list(candidates)
    if isinstance(candidates, list):
        candidates = [dict(c) if isinstance(c, Mapping) else c for c in candidates]
    return (query, candidates)


__all__ = ['TracedReranker']
