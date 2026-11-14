# ruff: noqa: BLE001
"""Metered LLM decorator (records usage around an inner LLM gateway)."""

from __future__ import annotations

import inspect
import logging
import uuid
from typing import Any

from .lite_llm_gateway import LiteLLMGateway

_LOGGER = logging.getLogger(__name__)


def _resolve_wrapped(kwargs: dict[str, Any], args: list[Any]) -> Any:
    wrapped = (
        kwargs.pop('wrapped', None)
        or kwargs.pop('gateway', None)
        or kwargs.pop('llm', None)
        or kwargs.pop('target', None)
        or kwargs.pop('inner', None)
    )
    if wrapped is None and args:
        wrapped = args.pop(0)
    return wrapped


def _metering_from(kwargs: dict[str, Any]) -> Any:
    metering = kwargs.pop('metering', None)
    if metering is None:
        metering = kwargs.pop('meter', None)
    if metering is None:
        metering = kwargs.pop('metering_port', None)
    if metering is None:
        metering = kwargs.pop('usage_metering', None)
    return metering


class MeteredLLM(LiteLLMGateway):
    """Decorator that records one usage row around an inner LLM gateway."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'gateway', 'llm', 'target', 'inner'):
            kwargs.pop(key, None)
        metering = _metering_from(kwargs)
        wrapped_args = args_list
        self.metering = metering
        self.wrapped = wrapped
        self._inner = wrapped
        if self._inner is None:
            super().__init__(*wrapped_args, **kwargs)

    def _inner_metering(self) -> Any:
        inner = self._inner
        if inner is None:
            return None
        return getattr(inner, 'metering', None)

    def _token_units(self) -> int:
        units = 1
        for source in (self._inner, getattr(self._inner, '_inner', None)):
            if source is None:
                continue
            rows = getattr(source, 'usage_rows', None)
            if isinstance(rows, list) and rows:
                last_row = rows[-1]
                if isinstance(last_row, dict):
                    for key in ('units', 'tokens_total', 'total_tokens'):
                        value = last_row.get(key)
                        if isinstance(value, int) and value > 0:
                            units = value
                            break
                    if units == 1:
                        prompt = 0
                        completion = 0
                        for key in ('tokens_prompt', 'prompt_tokens'):
                            value = last_row.get(key)
                            if isinstance(value, int):
                                prompt = max(prompt, value)
                        for key in ('tokens_completion', 'completion_tokens'):
                            value = last_row.get(key)
                            if isinstance(value, int):
                                completion = max(completion, value)
                        if prompt + completion > 0:
                            units = prompt + completion
        return units if units and units > 0 else 1

    async def _record_metering(self, company_id: Any, trace_id: Any = None) -> None:
        trace_id = trace_id or str(uuid.uuid4())
        metering = self.metering
        if metering is None or company_id is None:
            return
        if self._inner_metering() is metering:
            return
        target: Any = metering
        model = getattr(self._inner, 'model_id', None) or 'llm'
        units = self._token_units()
        try:
            method = None
            for name in (
                'record_usage',
                'record',
                'usage',
                'track_usage',
                'write_usage',
                'meter',
                'meter_call',
                'on_usage',
            ):
                candidate = getattr(target, name, None)
                if callable(candidate):
                    method = candidate
                    break
            if method is not None:
                try:
                    result = method(
                        company_id,
                        service='llm',
                        model=model,
                        model_name=model,
                        units=units,
                        estimated_cost=None,
                        cost=None,
                        trace_id=trace_id,
                        trace=trace_id,
                        trace_identifier=trace_id,
                    )
                except TypeError:
                    try:
                        result = method(company_id, service='llm', units=units, trace_id=trace_id)
                    except TypeError:
                        result = method(company_id, service='llm', units=units)
                if inspect.isawaitable(result):
                    await result
            elif callable(target):
                result = target(
                    {
                        'company_id': company_id,
                        'service': 'llm',
                        'units': units,
                        'trace_id': trace_id,
                    }
                )
                if inspect.isawaitable(result):
                    await result
        except Exception as exc:
            _LOGGER.debug('metered llm usage recording failed: %s', exc)

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        recorded = False
        try:
            return await target.complete(company_id, *args, **kwargs)
        finally:
            if not recorded:
                recorded = True
                try:
                    await self._record_metering(
                        company_id if company_id is not None else kwargs.get('company_id'),
                        trace_id=kwargs.get('trace_id', kwargs.get('trace')),
                    )
                except Exception as exc:
                    _LOGGER.debug('metered llm usage recording failed: %s', exc)

    async def stream(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        agg = target.stream(company_id, *args, **kwargs)
        inner_has_metering = self._inner_metering() is self.metering
        recorded = False
        async for item in agg:
            yield item
        if not recorded and not inner_has_metering and self.metering is not None:
            recorded = True
            try:
                await self._record_metering(
                    company_id if company_id is not None else kwargs.get('company_id'),
                    trace_id=kwargs.get('trace_id', kwargs.get('trace')),
                )
            except Exception as exc:
                _LOGGER.debug('metered llm stream usage recording failed: %s', exc)

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


__all__ = ['MeteredLLM']
