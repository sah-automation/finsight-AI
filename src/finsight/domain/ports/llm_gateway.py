"""Port for LLM completion and streaming."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class LLMGateway(ABC):
    """Interface for model completion and streaming (embeddings are separate)."""

    @abstractmethod
    async def complete(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        """Produce a complete model response."""
        raise NotImplementedError

    @abstractmethod
    async def stream(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        """Stream a model response."""
        raise NotImplementedError

    # Backwards-compatible alias methods (non-abstract).
    async def generate(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def chat(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def generate_text(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def stream_complete(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> object:
        return await self.stream(company_id, *args, **kwargs)

    async def stream_text(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.stream(company_id, *args, **kwargs)


# Backwards-compatible aliases.
LLM = LLMGateway


__all__ = ['LLM', 'LLMGateway']
