# ruff: noqa: BLE001, ANN401
from __future__ import annotations

import asyncio
from typing import Any

from .metered_llm import MeteredLLM as _Base


class RetryingLLM(_Base):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.retries = int(kwargs.pop('retries', kwargs.pop('max_retries', 1)) or 0)
        super().__init__(*args, **kwargs)

    async def complete(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        gateway = self._inner if self._inner is not None else self
        last_error = None
        for _ in range(self.retries + 1):
            try:
                return await gateway.complete(company_id, *args, **kwargs)
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.01)
        if last_error is not None:
            raise last_error
        return await gateway.complete(company_id, *args, **kwargs)


__all__ = ['RetryingLLM']
