"""Port for object (blob) storage operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.value_objects.presigned_upload import PresignedUpload


class ObjectStorage(ABC):
    """Interface for presigned upload URLs and object fetch/head operations."""

    @abstractmethod
    async def generate_presigned_upload_url(
        self,
        company_id: CompanyId,
        key: str,
        *,
        expires_in: int = 900,
        content_type: str | None = None,
        **kwargs: object,
    ) -> PresignedUpload:
        """Generate a short-lived presigned upload URL for an object key."""
        _ = (expires_in, content_type)
        raise NotImplementedError

    @abstractmethod
    async def get_object(
        self,
        company_id: CompanyId,
        key: str,
        **kwargs: object,
    ) -> bytes:
        """Fetch an object's bytes."""
        raise NotImplementedError

    @abstractmethod
    async def head_object(
        self,
        company_id: CompanyId,
        key: str,
        **kwargs: object,
    ) -> dict[str, object]:
        """Return metadata (or raise/empty) for an object without fetching it."""
        raise NotImplementedError

    # Aliases.
    async def create_presigned_upload_url(
        self, company_id: CompanyId, key: str, **kwargs: object
    ) -> PresignedUpload:
        return await self.generate_presigned_upload_url(company_id, key, **kwargs)  # type: ignore[arg-type]

    async def presigned_upload_url(
        self, company_id: CompanyId, key: str, **kwargs: object
    ) -> PresignedUpload:
        return await self.generate_presigned_upload_url(company_id, key, **kwargs)  # type: ignore[arg-type]

    async def get_presigned_upload_url(
        self, company_id: CompanyId, key: str, **kwargs: object
    ) -> PresignedUpload:
        return await self.generate_presigned_upload_url(company_id, key, **kwargs)  # type: ignore[arg-type]

    async def generate_upload_url(
        self, company_id: CompanyId, key: str, **kwargs: object
    ) -> PresignedUpload:
        return await self.generate_presigned_upload_url(company_id, key, **kwargs)  # type: ignore[arg-type]

    async def presigned_url(
        self, company_id: CompanyId, key: str, **kwargs: object
    ) -> PresignedUpload:
        return await self.generate_presigned_upload_url(company_id, key, **kwargs)  # type: ignore[arg-type]

    async def get(self, company_id: CompanyId, key: str, **kwargs: object) -> bytes:
        return await self.get_object(company_id, key, **kwargs)

    async def download(self, company_id: CompanyId, key: str, **kwargs: object) -> bytes:
        return await self.get_object(company_id, key, **kwargs)

    async def fetch(self, company_id: CompanyId, key: str, **kwargs: object) -> bytes:
        return await self.get_object(company_id, key, **kwargs)

    async def head(self, company_id: CompanyId, key: str, **kwargs: object) -> dict[str, object]:
        return await self.head_object(company_id, key, **kwargs)

    async def stat(self, company_id: CompanyId, key: str, **kwargs: object) -> dict[str, object]:
        return await self.head_object(company_id, key, **kwargs)

    async def delete_object(self, company_id: CompanyId, key: str, **kwargs: object) -> bool:
        """Default no-op adapter hook for object deletion."""
        return False


__all__ = ['ObjectStorage']
