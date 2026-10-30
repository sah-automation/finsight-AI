# ruff: noqa: ANN401, BLE001
"""Traced LLM decorator (outermost in the decorator stack)."""

from __future__ import annotations

import inspect
from typing import Any

from .lite_llm_gateway import LiteLLMGateway


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
        )
        args_list = list(args)
        if self.wrapped is None and args_list:
            self.wrapped = args_list.pop(0)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'gateway', 'llm', 'target', 'inner'):
            kwargs.pop(key, None)
        self.tracing = _tracer_from(kwargs, kwargs.get('config'), kwargs.get('container'))
        self.operation = str(kwargs.pop('operation', kwargs.pop('span_name', 'model_generation')))
        super().__init__(*args_list, **kwargs)
        self._inner = self.wrapped
        self._traced_operation = self.operation

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

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        await self._trace(company_id if company_id is not None else kwargs.get('company_id'))
        target = self._inner if self._inner is not None else self
        return await target.complete(company_id, *args, **kwargs)

    async def stream(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        await self._trace(company_id if company_id is not None else kwargs.get('company_id'))
        target = self._inner if self._inner is not None else self
        async for item in target.stream(company_id, *args, **kwargs):
            yield item

    async def generate(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        target = self._inner
        if target is None:
            raise AttributeError(name)
        return getattr(target, name)


__all__ = ['TracedLLM']
