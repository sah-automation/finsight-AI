"""Port for document (and document-version) persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.document_version import DocumentVersion


class DocumentRepository(ABC):
    """Interface for storing and retrieving documents and their versions."""

    @abstractmethod
    async def create_document_version(
        self,
        company_id: CompanyId,
        *,
        document_version: DocumentVersion | None = None,
        **kwargs: object,
    ) -> DocumentVersion:
        """Create a document version record."""
        _ = document_version
        raise NotImplementedError

    @abstractmethod
    async def get_document_version(
        self,
        company_id: CompanyId,
        version_id: object,
        **kwargs: object,
    ) -> DocumentVersion | None:
        """Fetch a single document version."""
        raise NotImplementedError

    @abstractmethod
    async def update_document_version(
        self,
        company_id: CompanyId,
        version_id: object,
        **kwargs: object,
    ) -> DocumentVersion | None:
        """Update a document version record."""
        raise NotImplementedError

    @abstractmethod
    async def list_document_versions(
        self,
        company_id: CompanyId,
        document_id: DocumentId | object | None = None,
        **kwargs: object,
    ) -> list[DocumentVersion]:
        """List versions for a document (or all versions for the company)."""
        raise NotImplementedError

    # Document-level convenience hooks (adapters may override; default safe).
    async def create_document(self, company_id: CompanyId, **kwargs: object) -> object:
        return None

    async def get_document(
        self, company_id: CompanyId, document_id: object, **kwargs: object
    ) -> object:
        return None

    async def update_document(
        self, company_id: CompanyId, document_id: object, **kwargs: object
    ) -> object:
        return None

    async def list_documents(self, company_id: CompanyId, **kwargs: object) -> list[object]:
        return []

    async def delete_document(
        self, company_id: CompanyId, document_id: object, **kwargs: object
    ) -> bool:
        return False

    # Aliases for version methods.
    async def create_version(self, company_id: CompanyId, **kwargs: object) -> DocumentVersion:
        return await self.create_document_version(company_id, **kwargs)  # type: ignore

    async def create_document_version_record(
        self, company_id: CompanyId, **kwargs: object
    ) -> DocumentVersion:
        return await self.create_document_version(company_id, **kwargs)  # type: ignore

    async def get_version(
        self, company_id: CompanyId, version_id: object, **kwargs: object
    ) -> DocumentVersion | None:
        return await self.get_document_version(company_id, version_id, **kwargs)

    async def get_document_version_by_id(
        self, company_id: CompanyId, version_id: object, **kwargs: object
    ) -> DocumentVersion | None:
        return await self.get_document_version(company_id, version_id, **kwargs)

    async def update_version(
        self, company_id: CompanyId, version_id: object, **kwargs: object
    ) -> DocumentVersion | None:
        return await self.update_document_version(company_id, version_id, **kwargs)

    async def update_document_version_state(
        self, company_id: CompanyId, version_id: object, **kwargs: object
    ) -> DocumentVersion | None:
        return await self.update_document_version(company_id, version_id, **kwargs)

    async def list_versions(
        self, company_id: CompanyId, document_id: object = None, **kwargs: object
    ) -> list[DocumentVersion]:
        return await self.list_document_versions(company_id, document_id, **kwargs)

    async def find_versions(
        self, company_id: CompanyId, document_id: object = None, **kwargs: object
    ) -> list[DocumentVersion]:
        return await self.list_document_versions(company_id, document_id, **kwargs)


__all__ = ['DocumentRepository']
