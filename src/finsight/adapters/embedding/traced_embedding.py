# ruff: noqa: BLE001
from __future__ import annotations

import inspect
from typing import Any

from .lite_llm_embedding import LiteLLMEmbedding


def _resolve_wrapped(kwargs: dict[str, Any], args: list[Any]) -> Any:
    wrapped = (
        kwargs.pop('wrapped', None)
        or kwargs.pop('embedding', None)
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


class TracedEmbedding(LiteLLMEmbedding):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'embedding', 'target', 'inner'):
            kwargs.pop(key, None)
        self.tracing = _tracer_from(kwargs)
        self.operation = str(kwargs.pop('operation', 'embedding'))
        super().__init__(*args, **kwargs)
        self.wrapped = wrapped
        self._inner = wrapped

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
        except Exception:
            return

    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        await self._trace(company_id if company_id is not None else kwargs.get('company_id'))
        target = self._inner if self._inner is not None else self
        return await target.embed(company_id, *args, **kwargs)

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

    @property
    def _wrapped(self) -> Any:
        return getattr(self, '_inner', None)


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
        for field in getattr(switches, 'model_fields', {}) or {}:
            result[str(field)] = getattr(switches, field, None)
    except Exception:  # noqa: S110
        pass
    return result


def _standard_attributes(obj: Any, company_id: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {'step': getattr(obj, 'operation', None)}
    inner = getattr(obj, '_inner', None)
    model = (
        getattr(inner, 'model_id', None)
        or getattr(inner, 'model', None)
        or getattr(obj, 'model', None)
    )
    if model is not None:
        attrs['model_name'] = model
        attrs['model'] = model
    switches = None
    if isinstance(getattr(obj, '_kwargs', None), dict):
        switches = obj._kwargs.get('config')
    if switches is None:
        switches = getattr(inner, 'config', None) or getattr(obj, '_config', None)
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


__all__ = ['TracedEmbedding']
