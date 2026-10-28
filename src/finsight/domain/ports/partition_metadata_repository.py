"""Port for partition metadata access."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from finsight.core.types import CompanyId, PartitionStatus

if TYPE_CHECKING:
    from finsight.domain.entities.partition_metadata import PartitionMetadata


class PartitionMetadataRepository(ABC):
    """Interface for storing and retrieving partition metadata."""

    @abstractmethod
    async def record_partition(
        self,
        company_id: CompanyId,
        partition_name: str,
        table_name: str,
        status: PartitionStatus = PartitionStatus.CREATING,
    ) -> PartitionMetadata:
        """Record a partition creation attempt."""
        raise NotImplementedError

    @abstractmethod
    async def get_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> PartitionMetadata | None:
        """Get partition metadata for a company and table."""
        raise NotImplementedError

    @abstractmethod
    async def list_partitions_for_company(
        self,
        company_id: CompanyId,
    ) -> list[PartitionMetadata]:
        """List all partitions for a company."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(
        self,
        company_id: CompanyId,
        table_name: str,
        status: PartitionStatus,
    ) -> PartitionMetadata | None:
        """Update partition status."""
        raise NotImplementedError
