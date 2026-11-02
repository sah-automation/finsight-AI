"""Port (seam) for carrying pipeline run state between steps/processes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StateStore(ABC):
    """Small seam for storing a pipeline run context."""

    @abstractmethod
    async def get(self, key: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: Any, value: Any) -> Any:
        raise NotImplementedError

    async def load(self, key: Any) -> Any:
        return await self.get(key)

    async def save(self, key: Any, value: Any) -> Any:
        return await self.set(key, value)

    async def put(self, key: Any, value: Any) -> Any:
        return await self.set(key, value)

    async def fetch(self, key: Any) -> Any:
        return await self.get(key)

    async def delete(self, key: Any) -> None:
        raise NotImplementedError


PipelineStateStore = StateStore
StepStateStore = StateStore
RunStateStore = StateStore
ContextStore = StateStore
StepContextStore = StateStore


__all__ = [
    'ContextStore',
    'PipelineStateStore',
    'RunStateStore',
    'StateStore',
    'StepContextStore',
    'StepStateStore',
]
