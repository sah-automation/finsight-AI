"""Port for partition management."""

from __future__ import annotations

from abc import ABC, abstractmethod

from finsight.core.types import CompanyId


class PartitionGateway(ABC):
    """Interface for creating and managing per-company partitions."""

    @abstractmethod
    async def create_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> str:
        """Create a partition for a company on the given table. Returns partition name."""
        raise NotImplementedError

    @abstractmethod
    async def ensure_partition_exists(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> bool:
        """Ensure partition exists (idempotent). Returns True if exists/created."""
        raise NotImplementedError

    @abstractmethod
    async def drop_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> bool:
        """Drop a partition for a company. Returns True if dropped."""
        raise NotImplementedError

    @abstractmethod
    async def list_partitions(
        self,
        company_id: CompanyId,
    ) -> list[str]:
        """List all partitions for a company."""
        raise NotImplementedError


# Backwards compatibility alias
PartitionManager = PartitionGateway
