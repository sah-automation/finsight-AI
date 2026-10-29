# ruff: noqa: ANN401
from __future__ import annotations

from typing import Any

from .litellm_gateway import (
    LiteLLMGateway,
)


class MeteredLLM(LiteLLMGateway):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.wrapped = (
            kwargs.pop('gateway', None) or kwargs.pop('llm', None) or kwargs.pop('target', None)
        )
        if self.wrapped is None and args and not hasattr(args[0], 'config'):
            self.wrapped = args[0]
            args = args[1:]
        super().__init__(*args, **kwargs)
        if self.wrapped is not None:
            self.chains = getattr(self.wrapped, 'chains', self.chains)
            self.metering = getattr(self.wrapped, 'metering', self.metering)
        self._inner = self.wrapped

    async def stream(self, company_id: object = None, *args: object, **kwargs: object) -> object:
        gateway = self._inner if self._inner is not None else self
        return gateway.stream(company_id, *args, **kwargs)

    async def complete(self, company_id: object = None, *args: object, **kwargs: object) -> object:
        gateway = self._inner if self._inner is not None else self
        return await gateway.complete(company_id, *args, **kwargs)


__all__ = ['MeteredLLM']
