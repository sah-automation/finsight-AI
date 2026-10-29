"""Port for text embedding generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class EmbeddingProvider(ABC):
    """Interface for embedding text into vectors."""

    @abstractmethod
    async def embed(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        """Embed input text(s) and return vectors."""
        raise NotImplementedError

    # Backwards-compatible aliases.
    async def embed_texts(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.embed(company_id, *args, **kwargs)

    async def embed_text(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.embed(company_id, *args, **kwargs)

    async def embed_batch(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.embed(company_id, *args, **kwargs)

    async def embed_many(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.embed(company_id, *args, **kwargs)


# Backwards-compatible aliases.
EmbeddingGateway = EmbeddingProvider
Embeddings = EmbeddingProvider

__all__ = ['EmbeddingGateway', 'EmbeddingProvider', 'Embeddings']
