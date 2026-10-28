"""Port for virus/malware scanning of stored objects."""

from __future__ import annotations

from abc import ABC, abstractmethod

from finsight.core.types import CompanyId
from finsight.domain.value_objects.virus_scan_result import VirusScanResult


class VirusScanner(ABC):
    """Interface for scanning an object by company and key."""

    @abstractmethod
    async def scan(
        self,
        company_id: CompanyId,
        key: str,
        *,
        bucket: str | None = None,
        **kwargs: object,
    ) -> VirusScanResult:
        """Scan an object and return a :class:`VirusScanResult`."""
        _ = bucket
        raise NotImplementedError

    async def scan_object(
        self, company_id: CompanyId, key: str, **kwargs: object
    ) -> VirusScanResult:
        return await self.scan(company_id, key, **kwargs)  # type: ignore

    async def scan_key(self, company_id: CompanyId, key: str, **kwargs: object) -> VirusScanResult:
        return await self.scan(company_id, key, **kwargs)  # type: ignore


__all__ = ['VirusScanner']
