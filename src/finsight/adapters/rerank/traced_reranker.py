from __future__ import annotations

import inspect
from typing import Any


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
            result = method(company_id, self.operation)
            if inspect.isawaitable(result):
                await result
        except Exception:
            return

    async def rerank(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        await self._trace(company_id if company_id is not None else kwargs.get('company_id'))
        target = self._inner if self._inner is not None else self
        return await target.rerank(company_id, *args, **kwargs)

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


__all__ = ['TracedReranker']
