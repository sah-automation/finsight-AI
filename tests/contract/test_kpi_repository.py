"""Contract tests for the KPI repository port.

A KPI row uses the exact decimal-string value and provenance fields from
ADR-0008/0009. The primary adapter is exercised through its in-memory seam so
the shared contract runs without a database; a wired session uses the same
methods against ``kpi_values``/``kpi_current`` with RLS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from finsight.adapters.repositories.kpi_repository import KpiRepository

from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports.kpi_repository import KpiRepository as KpiRepositoryPort

pytestmark = pytest.mark.contract

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
OTHER_COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000002')


def _row(
    *,
    company: CompanyId = COMPANY,
    kpi_code: str = 'revenue',
    period: str = '2025-Q1',
    period_start: str = '2025-01-01',
    document_version_id: str = '10000000-0000-4000-8000-000000000001',
    chart_period: str | None = None,
    chart_period_start: str | None = None,
    value: str | None = '100.00',
    computation_status: str = 'computed',
    currency: str = 'USD',
    units: str = 'USD',
    citations: list[str] | None = None,
    computation_rule_version: str = 'rule-v1',
    superseded_by: str | None = None,
) -> dict[str, Any]:
    """Build one storage-key-shaped KPI row with documented defaults."""
    bucket = chart_period or period
    return {
        'company_id': str(company),
        'kpi_code': kpi_code,
        'period': period,
        'document_version_id': document_version_id,
        'chart_period': bucket,
        'period_start': period_start,
        'chart_period_start': chart_period_start or period_start,
        'currency': currency,
        'units': units,
        'value': value,
        'computation_status': computation_status,
        'estimation_method': None,
        'source_citations': ['cite-1'] if citations is None else citations,
        'computation_rule_version': computation_rule_version,
        'superseded_by_document_version_id': superseded_by,
    }


@pytest.fixture
def repository() -> KpiRepositoryPort:
    return KpiRepository()


class TestKpiRepositoryContract:
    async def test_upsert_batch_is_idempotent_on_storage_key(
        self, repository: KpiRepositoryPort
    ) -> None:
        row = _row()

        assert await repository.upsert_batch([row]) == 1
        assert await repository.upsert_batch([{**row, 'value': '125.00'}]) == 1

        current = await repository.get_current(COMPANY)
        assert len(current) == 1
        assert current[0]['value'] == '125.00'
