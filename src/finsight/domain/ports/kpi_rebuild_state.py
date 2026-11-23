"""Port for the global KPI computation-rule rebuild gate.

A new ``computation_rule_version`` stays ``pending`` until its rolling rebuild
starts, and cannot activate until it reaches ``complete``. The table is global
rather than tenant-scoped, so this port has no ``company_id`` arguments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

KpiRebuildStateValue = Literal['pending', 'running', 'complete']


class KpiRebuildState(ABC):
    """Lifecycle store for KPI computation-rule versions."""

    @abstractmethod
    async def get(self, version: str) -> KpiRebuildStateValue | None:
        """Return the stored state for ``version`` or ``None`` when unknown."""
        raise NotImplementedError

    @abstractmethod
    async def is_complete(self, version: str) -> bool:
        """Return whether ``version`` has finished its rebuild."""
        raise NotImplementedError

    @abstractmethod
    async def ensure_pending(self, version: str) -> None:
        """Record ``version`` as pending without downgrading a later state."""
        raise NotImplementedError

    @abstractmethod
    async def mark_running(self, version: str) -> None:
        """Start the rebuild for ``version`` without downgrading completion."""
        raise NotImplementedError

    @abstractmethod
    async def mark_complete(self, version: str) -> None:
        """Mark the rebuild for ``version`` finished."""
        raise NotImplementedError

    @abstractmethod
    async def incomplete_versions(self) -> list[str]:
        """Return pending/running versions awaiting a complete rebuild."""
        raise NotImplementedError


KpiRebuildStatePort = KpiRebuildState

__all__ = ['KpiRebuildState', 'KpiRebuildStatePort', 'KpiRebuildStateValue']
