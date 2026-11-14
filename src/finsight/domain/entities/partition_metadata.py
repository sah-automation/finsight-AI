"""Partition metadata entity - pure domain object, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from finsight.core.types import CompanyId, PartitionStatus

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class PartitionMetadata:
    """Tracks per-company partition creation."""

    company_id: CompanyId
    partition_name: str
    table_name: str
    status: PartitionStatus = PartitionStatus.CREATING
    created_at: datetime | None = None
    updated_at: datetime | None = None
