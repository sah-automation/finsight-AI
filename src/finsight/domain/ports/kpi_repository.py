"""Port for reading and writing code-computed KPI rows.

Rows are plain mappings carrying the ADR-0008/0009 fields. The storage key is
``(company_id, kpi_code, period, document_version_id, chart_period)``; writes
are upserts on that key and never delete history.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from finsight.core.types import CompanyId

KpiRow = dict[str, Any]
KpiRows = list[KpiRow]

# Stable fields covered by a chart Freshness Fingerprint (issue #378, Phase 2
# spec §2). Timestamps and the injected Display Label are deliberately absent.
# The repository projection and the hashing service both derive from this tuple.
FINGERPRINT_FIELDS = (
    'kpi_code',
    'period',
    'chart_period',
    'document_version_id',
    'computation_rule_version',
    'value',
    'computation_status',
    'source_citations',
    'conflict_marker',
    'superseded_by_document_version_id',
)


class KpiRepository(ABC):
    """Tenant-scoped KPI store read/write interface."""

    @abstractmethod
    async def upsert_batch(
        self,
        rows: Sequence[KpiRow],
        *,
        company_id: CompanyId | None = None,
        **kwargs: Any,
    ) -> int:
        """Upsert rows on the storage key and return the number written.

        ``company_id`` is optional because each row already carries it; when
        supplied it is enforced against every row before writing.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_current(
        self,
        company_id: CompanyId,
        filters: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> KpiRows:
        """Return current rows from ``kpi_current`` with additive filters."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_company_codes_periods(
        self,
        company_id: CompanyId,
        kpi_codes: Sequence[str],
        period_from: str | None = None,
        period_to: str | None = None,
        **kwargs: Any,
    ) -> KpiRows:
        """Return current rows for KPI codes in a declared-period range."""
        raise NotImplementedError

    @abstractmethod
    async def get_fingerprint_data(
        self,
        company_id: CompanyId,
        chart_specs: Sequence[Any],
        **kwargs: Any,
    ) -> dict[str, KpiRows]:
        """Return the rows backing each chart's freshness fingerprint."""
        raise NotImplementedError


# Ticket-facing alias; the concrete class name follows the repo's file/class rule.
KpiRepositoryPort = KpiRepository

__all__ = [
    'FINGERPRINT_FIELDS',
    'KpiRepository',
    'KpiRepositoryPort',
    'KpiRow',
    'KpiRows',
]
