from typing import Any

from .lite_llm_gateway import LiteLLMGateway


class CachedLLM(LiteLLMGateway):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.pop('cache', kwargs.pop('answer_cache', None))
        self.wrapped = (
            kwargs.pop('gateway', None) or kwargs.pop('llm', None) or kwargs.pop('target', None)
        )
        if (
            self.wrapped is None
            and args
            and (hasattr(args[0], 'complete') or hasattr(args[0], 'stream'))
        ):
            self.wrapped = args[0]
            args = args[1:]
        if self.wrapped is not None:
            self._inner = self.wrapped
        else:
            self._inner = None
            super().__init__(*args, **kwargs)

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        gateway = self._inner if self._inner is not None else self
        if gateway is self:
            return await super().complete(company_id, *args, **kwargs)
        return await gateway.complete(company_id, *args, **kwargs)

    async def stream(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        gateway = self._inner if self._inner is not None else self
        if gateway is self:
            async for item in super().stream(company_id, *args, **kwargs):  # type: ignore[attr-defined]
                yield item
            return
        async for item in gateway.stream(company_id, *args, **kwargs):
            yield item

    async def generate(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def chat(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        try:
            inner = object.__getattribute__(self, '_inner')
        except AttributeError:
            raise AttributeError(name) from None
        if inner is None or inner is self:
            raise AttributeError(name)
        return getattr(inner, name)


__all__ = ['CachedLLM']
