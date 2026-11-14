"""In-memory default implementation of the state-store seam."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.state_store import StateStore as _StateStorePort


class InMemoryStateStore(_StateStorePort):
    """Process-local, in-memory state store (default implementation)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._data: dict[Any, Any] = {}

    async def get(self, key: Any) -> Any:
        return self._data.get(key)

    async def set(self, key: Any, value: Any) -> Any:
        self._data[key] = value
        return value

    async def delete(self, key: Any) -> None:
        self._data.pop(key, None)

    # Optional/common aliases
    async def load(self, key: Any) -> Any:
        return await self.get(key)

    async def save(self, key: Any, value: Any) -> Any:
        return await self.set(key, value)

    async def put(self, key: Any, value: Any) -> Any:
        return await self.set(key, value)

    async def fetch(self, key: Any) -> Any:
        return await self.get(key)

    async def remove(self, key: Any) -> None:
        await self.delete(key)

    async def discard(self, key: Any) -> None:
        await self.delete(key)

    def clear(self) -> None:
        self._data.clear()

    def snapshot(self) -> dict[Any, Any]:
        return dict(self._data)


# Alias class names.
InMemoryStepStateStore = InMemoryStateStore
InMemoryPipelineStateStore = InMemoryStateStore
InMemoryContextStore = InMemoryStateStore
InMemoryRunStateStore = InMemoryStateStore
ContextStoreImpl = InMemoryStateStore
StateStoreImpl = InMemoryStateStore

StateStore: Any = InMemoryStateStore


__all__ = [
    'ContextStoreImpl',
    'InMemoryContextStore',
    'InMemoryPipelineStateStore',
    'InMemoryRunStateStore',
    'InMemoryStateStore',
    'InMemoryStepStateStore',
    'StateStore',
    'StateStoreImpl',
]
