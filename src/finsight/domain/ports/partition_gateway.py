"""Port for partition management."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    @abstractmethod
    async def record_partition_metadata(
        self,
        company_id: CompanyId,
        partition_name: str,
        table_name: str,
    ) -> None:
        """Record partition metadata."""
        raise NotImplementedError


# Backwards compatibility alias
PartitionManager = PartitionGateway
