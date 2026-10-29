# ruff: noqa: ANN401
from __future__ import annotations

from typing import Any

from .litellm_embedding import LiteLLMEmbedding


class MeteredEmbedding(LiteLLMEmbedding):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.wrapped = kwargs.pop('embedding', None) or kwargs.pop('target', None)
        if self.wrapped is None and args and not hasattr(args[0], 'config'):
            self.wrapped = args[0]
            args = args[1:]
        super().__init__(*args, **kwargs)
        self._inner = self.wrapped

    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        target = self._inner if self._inner is not None else self
        return await target.embed(company_id, *args, **kwargs)


__all__ = ['MeteredEmbedding']
