"""Company (tenant) entity - pure domain object, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from finsight.core.types import CompanyId


@dataclass(frozen=True)
class Company:
    """Tenant boundary; every data access is scoped by ``company_id``."""

    id: CompanyId
    name: str
    slug: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
