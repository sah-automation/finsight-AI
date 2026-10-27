"""Partition metadata entity - pure domain object, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from finsight.core.types import CompanyId


@dataclass(frozen=True)
class PartitionMetadata:
    """Tracks per-company partition creation."""

    company_id: CompanyId
    partition_name: str
    table_name: str
    status: str = 'creating'
    created_at: datetime | None = None
    updated_at: datetime | None = None
