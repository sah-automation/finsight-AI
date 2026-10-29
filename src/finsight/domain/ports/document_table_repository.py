"""Port for document-table persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.domain.entities.document_table import DocumentTable


class DocumentTableRepository(ABC):
    """Interface for persisting normalised document tables."""

    @abstractmethod
    async def upsert_document_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable:
        raise NotImplementedError

    @abstractmethod
    async def upsert_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> list[DocumentTable]:
        raise NotImplementedError

    @abstractmethod
    async def get_document_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        raise NotImplementedError

    @abstractmethod
    async def list_document_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> list[DocumentTable]:
        raise NotImplementedError

    @abstractmethod
    async def mark_document_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def mark_version_document_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        raise NotImplementedError

    async def upsert_table(self, company_id: object, *args: object, **kwargs: object) -> object:
        return await self.upsert_document_table(company_id, *args, **kwargs)

    async def upsert_tables(self, company_id: object, *args: object, **kwargs: object) -> object:
        return await self.upsert_document_tables(company_id, *args, **kwargs)

    async def list_tables(
        self, company_id: object, *args: object, **kwargs: object
    ) -> list[DocumentTable]:
        return await self.list_document_tables(company_id, *args, **kwargs)

    async def get_table(
        self, company_id: object, *args: object, **kwargs: object
    ) -> DocumentTable | None:
        return await self.get_document_table(company_id, *args, **kwargs)

    async def mark_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self.mark_document_tables_inactive(company_id, *args, **kwargs)

    async def mark_version_tables_inactive(
        self, company_id: object, *args: object, **kwargs: object
    ) -> int:
        return await self.mark_version_document_tables_inactive(company_id, *args, **kwargs)


DocumentTablesRepository = DocumentTableRepository
DocumentTablesRepositoryPort = DocumentTableRepository
TableRepository = DocumentTableRepository
TablesRepository = DocumentTableRepository


__all__ = [
    'DocumentTableRepository',
    'DocumentTablesRepository',
    'DocumentTablesRepositoryPort',
    'TableRepository',
    'TablesRepository',
]
