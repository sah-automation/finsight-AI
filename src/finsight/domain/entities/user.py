"""User entity - pure domain object, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from finsight.core.types import CompanyId, Role, UserId


@dataclass(frozen=True)
class User:
    """A user belonging to (exactly) one company."""

    id: UserId
    company_id: CompanyId
    email: str
    role: Role
    created_at: datetime | None = None
    updated_at: datetime | None = None
