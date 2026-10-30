# ruff: noqa: ANN401, BLE001
from __future__ import annotations

import asyncio
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


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


class RetryingEmbedding:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'embedding', 'target', 'inner'):
            kwargs.pop(key, None)
        self.retries = int(kwargs.pop('retries', kwargs.pop('max_retries', 1)) or 0)
        self.delay = float(kwargs.pop('retry_delay', kwargs.pop('delay', 0.01)) or 0.01)
        self._config = kwargs.get('config')
        self._kwargs = kwargs
        self._inner = wrapped

    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        last_error = None
        for _ in range(self.retries + 1):
            try:
                return await target.embed(company_id, *args, **kwargs)
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(self.delay)
        if last_error is not None:
            try:
                _LOGGER.warning(
                    'embedding retries exceeded',
                    extra={
                        'embedding_retries': self.retries + 1,
                        'embedding_retries_exceeded': self.retries + 1,
                        'alert': 'embedding_retries_exceeded',
                    },
                )
            except Exception as exc:  # pragma: no cover - best-effort logging
                _LOGGER.debug('embedding retry alert log failed', exc_info=exc)
            raise last_error
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


__all__ = ['RetryingEmbedding']
