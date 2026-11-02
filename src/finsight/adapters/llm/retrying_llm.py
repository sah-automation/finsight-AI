# ruff: noqa: BLE001
"""Retrying LLM decorator."""

from __future__ import annotations

import asyncio
from typing import Any

from .lite_llm_gateway import LiteLLMGateway


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


class RetryingLLM(LiteLLMGateway):
    """Decorator that retries complete() on the inner LLM gateway."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        args_list: Any = list(args)
        wrapped = _resolve_wrapped(kwargs, args_list)
        kwargs = dict(kwargs)
        for key in ('wrapped', 'gateway', 'llm', 'target', 'inner'):
            kwargs.pop(key, None)
        self.retries = int(kwargs.pop('retries', kwargs.pop('max_retries', 1)) or 0)
        self.delay = float(kwargs.pop('retry_delay', kwargs.pop('delay', 0.01)) or 0.01)
        super().__init__(*args, **kwargs)
        self.wrapped = wrapped
        self._inner = wrapped

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                return await target.complete(company_id, *args, **kwargs)
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(self.delay)
        if last_error is not None:
            raise last_error
        return await target.complete(company_id, *args, **kwargs)

    async def stream(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        async for item in target.stream(company_id, *args, **kwargs):
            yield item

    def __getattr__(self, name: str) -> Any:
        target = self._inner
        if target is None:
            raise AttributeError(name)
        return getattr(target, name)


__all__ = ['RetryingLLM']
