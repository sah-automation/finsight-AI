"""Port for reading/extracting content from documents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from finsight.core.types import CompanyId
from finsight.domain.value_objects.reader_result import ReaderResult


class DocumentReader(ABC):
    """Interface for extracting text, tables and page numbers from a document."""

    @abstractmethod
    async def read(
        self,
        company_id: CompanyId,
        content: object = None,
        *,
        file_path: str | None = None,
        filename: str | None = None,
        file_name: str | None = None,
        content_type: str | None = None,
        **kwargs: object,
    ) -> ReaderResult:
        """Read a document and return a :class:`ReaderResult`."""
        _ = (file_path, filename, file_name, content_type)
        raise NotImplementedError

    # Convenience aliases (default implementations delegate to ``read``).
    async def read_document(
        self, company_id: CompanyId, content: object = None, **kwargs: object
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)  # type: ignore

    async def extract(
        self, company_id: CompanyId, content: object = None, **kwargs: object
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)  # type: ignore

    async def parse(
        self, company_id: CompanyId, content: object = None, **kwargs: object
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)  # type: ignore

    async def extract_text(
        self, company_id: CompanyId, content: object = None, **kwargs: object
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)  # type: ignore


__all__ = ['DocumentReader']
