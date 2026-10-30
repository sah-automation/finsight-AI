# ruff: noqa: S110
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


def _metering_from(kwargs: dict[str, Any]) -> Any:
    for key in ('metering', 'meter', 'metering_port', 'usage_metering'):
        if kwargs.get(key) is not None:
            return kwargs.pop(key)
    return None


class MeteredReranker:
    """Decorator that records one usage row around an inner reranker."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'reranker', 'ranker', 'target', 'inner'):
            kwargs.pop(key, None)
        self.metering = _metering_from(kwargs)
        self.wrapped = wrapped
        self._inner = wrapped
        self._config = kwargs.get('config')
        self._kwargs = kwargs

    def _inner_metering(self) -> Any:
        inner = self._inner
        if inner is None:
            return None
        return getattr(inner, 'metering', None)

    async def _record_usage(self, company_id: Any) -> None:
        metering = self.metering
        if metering is None or self._inner_metering() is metering:
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
                        company_id, service='rerank', model='rerank', units=1, estimated_cost=None
                    )
                except TypeError:
                    result = method(company_id, service='rerank', units=1)
                if inspect.isawaitable(result):
                    await result
        except Exception:
            pass

    async def rerank(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        try:
            return await target.rerank(company_id, *args, **kwargs)
        finally:
            await self._record_usage(
                company_id if company_id is not None else kwargs.get('company_id')
            )

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


__all__ = ['MeteredReranker']
