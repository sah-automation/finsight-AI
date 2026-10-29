# ruff: noqa: ANN401
from __future__ import annotations

from typing import Any

from .litellm_gateway import LiteLLMGateway


class CachedLLM(LiteLLMGateway):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.cache = kwargs.pop('cache', kwargs.pop('answer_cache', None))
        self.wrapped = (
            kwargs.pop('gateway', None) or kwargs.pop('llm', None) or kwargs.pop('target', None)
        )
        if self.wrapped is None and args and not hasattr(args[0], 'config'):
            self.wrapped = args[0]
            args = args[1:]
        super().__init__(*args, **kwargs)
        if self.wrapped is not None:
            self._inner = self.wrapped
        else:
            self._inner = None

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        gateway = self._inner if self._inner is not None else self
        return await gateway.complete(company_id, *args, **kwargs)


__all__ = ['CachedLLM']
