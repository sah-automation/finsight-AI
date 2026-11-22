"""Authenticated principal resolved for Phase 2 API entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class ApiPrincipal:
    """Identity and role capabilities derived from authenticated claims."""

    company_id: str
    user_id: str | None
    role_id: str
    access_scope: tuple[str, ...]
    role_actions: tuple[str, ...]
    category_permissions: Mapping[str, tuple[str, ...]]
