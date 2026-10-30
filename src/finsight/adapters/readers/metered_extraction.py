from __future__ import annotations

import inspect
from typing import Any


def _resolve_wrapped(kwargs: dict[str, Any], args: list[Any]) -> Any:
    wrapped = (
        kwargs.pop('wrapped', None)
        or kwargs.pop('reader', None)
        or kwargs.pop('extractor', None)
        or kwargs.pop('target', None)
        or kwargs.pop('inner', None)
    )
    if wrapped is None and args:
        wrapped = args.pop(0)
    return wrapped


def _metering_from(kwargs: dict[str, Any]) -> Any:
    for key in ('metering', 'meter', 'metering_port', 'usage_metering'):
        if kwargs.get(key) is not None:
            return kwargs.pop(key)
    return None


class MeteredExtraction:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'reader', 'extractor', 'target', 'inner'):
            kwargs.pop(key, None)
        self.metering = _metering_from(kwargs)
        self._inner = wrapped

    def _inner_metering(self) -> Any:
        inner = self._inner
        if inner is None:
            return None
        return getattr(inner, 'metering', None)

    async def _record_usage(self, company_id: Any, trace_id: Any = None) -> None:
        metering = self.metering
        import uuid

        if trace_id is None:
            trace_id = str(uuid.uuid4())
        if metering is None or self._inner_metering() is metering or company_id is None:
            return
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
                candidate = getattr(metering, name, None)
                if callable(candidate):
                    method = candidate
                    break
            if method is not None:
                try:
                    result = method(
                        company_id,
                        service='extraction',
                        model='extraction',
                        units=1,
                        estimated_cost=None,
                    )
                except TypeError:
                    result = method(company_id, service='extraction', units=1)
                if inspect.isawaitable(result):
                    await result
        except Exception:
            pass

    async def _delegate(self, method_name: str, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        method = getattr(target, method_name, None)
        if not callable(method):
            raise AttributeError(method_name)  # noqa: TRY004
        try:
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        finally:
            await self._record_usage(
                company_id, trace_id=kwargs.get('trace_id', kwargs.get('trace'))
            )

    async def read(self, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
        company_id = (
            company_id
            if company_id is not None
            else kwargs.get('company_id', kwargs.get('company'))
        )
        if company_id is None and args:
            company_id = args[0] if not isinstance(args[0], str) else None
        return await self._delegate('read', company_id, *args, **kwargs)

    async def extract(self, *args: Any, company_id: Any = None, **kwargs: Any) -> Any:
        company_id = (
            company_id
            if company_id is not None
            else kwargs.get('company_id', kwargs.get('company'))
        )
        if company_id is None and args:
            company_id = args[0] if not isinstance(args[0], str) else None
        return await self._delegate('extract', company_id, *args, **kwargs)

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


MeteredTextract = MeteredExtraction
MeteredReader = MeteredExtraction
__all__ = ['MeteredExtraction', 'MeteredReader', 'MeteredTextract']
