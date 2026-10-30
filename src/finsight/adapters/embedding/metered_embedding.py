# ruff: noqa: ANN401, BLE001, PLC0415, S110
from __future__ import annotations

from typing import Any

from .litellm_embedding import LiteLLMEmbedding


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


def _metering_from(kwargs: dict[str, Any]) -> Any:
    metering = kwargs.pop('metering', None)
    if metering is None:
        metering = kwargs.pop('meter', None)
    if metering is None:
        metering = kwargs.pop('metering_port', None)
    return metering


class MeteredEmbedding(LiteLLMEmbedding):
    """Decorator that records one usage row around an inner embedding adapter."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'embedding', 'target', 'inner'):
            kwargs.pop(key, None)
        metering = _metering_from(kwargs)
        super().__init__(*args, **kwargs)
        self.metering = metering
        self.wrapped = wrapped
        self._inner = wrapped

    def _inner_metering(self) -> Any:
        inner = self._inner
        if inner is None:
            return None
        return getattr(inner, 'metering', None)

    async def _record_metering(self, company_id: Any, units: int = 1, trace_id: Any = None) -> None:
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
                        service='embedding',
                        model='embedding',
                        units=units,
                        estimated_cost=None,
                    )
                except TypeError:
                    result = method(company_id, service='embedding', units=units)
                import inspect

                if inspect.isawaitable(result):
                    await result
            elif callable(metering):
                import inspect

                result = metering(
                    {'company_id': company_id, 'service': 'embedding', 'units': units}
                )
                if inspect.isawaitable(result):
                    await result
        except Exception:
            pass

    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        units = 1
        try:
            units = (
                len(kwargs.get('texts') or kwargs.get('inputs') or kwargs.get('input') or []) or 1
            )
            if isinstance(args[0] if args else None, (list, tuple)):
                units = len(args[0])
        except Exception:
            units = 1
        units = max(units, 1)
        try:
            return await target.embed(company_id, *args, **kwargs)
        finally:
            await self._record_metering(
                company_id if company_id is not None else kwargs.get('company_id'), units=units
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


__all__ = ['MeteredEmbedding']
