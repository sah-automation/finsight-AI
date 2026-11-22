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
    metric_ids: list[str] | None = None,
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
        'source_citations': ['cit:v1:10000000-0000-4000-8000-000000000001:p1']
        if citations is None
        else citations,
        'source_metric_ids': ['metric-1'] if metric_ids is None else metric_ids,
        'computation_rule_version': computation_rule_version,
        'superseded_by_document_version_id': superseded_by,
    }


@pytest.fixture
def repository() -> KpiRepositoryPort:
    return KpiRepository()


_FINGERPRINT_FIELDS = {
    'kpi_code',
    'period',
    'chart_period',
    'document_version_id',
    'computation_rule_version',
    'value',
    'computation_status',
    'source_citations',
    'source_metric_ids',
    'conflict_marker',
    'superseded_by_document_version_id',
}


async def _seed(repository: KpiRepositoryPort) -> None:
    await repository.upsert_batch(
        [
            _row(kpi_code='revenue', period='2025-Q1', period_start='2025-01-01'),
            _row(kpi_code='revenue', period='2025-Q2', period_start='2025-04-01', value='120.00'),
            _row(
                kpi_code='gross_margin', period='2025-Q1', period_start='2025-01-01', value='40.00'
            ),
            _row(
                kpi_code='revenue',
                period='2025-Q1',
                period_start='2025-01-01',
                document_version_id='10000000-0000-4000-8000-000000000099',
                value='95.00',
                computation_rule_version='rule-v2',
            ),
            _row(company=OTHER_COMPANY, value='900.00'),
        ]
    )


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

    async def test_upsert_rejects_another_tenant(self, repository: KpiRepositoryPort) -> None:
        with pytest.raises(ValueError):
            await repository.upsert_batch([_row(company=OTHER_COMPANY)], company_id=COMPANY)

    async def test_get_current_is_company_isolated(self, repository: KpiRepositoryPort) -> None:
        await _seed(repository)

        current = await repository.get_current(COMPANY)

        assert current
        assert all(row['company_id'] == str(COMPANY) for row in current)
        assert all(row['value'] != '900.00' for row in current)

    async def test_get_current_combines_filters(self, repository: KpiRepositoryPort) -> None:
        await _seed(repository)

        by_code_and_period = await repository.get_current(
            COMPANY, {'kpi_codes': ['revenue'], 'period_from': '2025-04-01'}
        )
        by_code_and_status = await repository.get_current(
            COMPANY, {'kpi_code': 'gross_margin', 'computation_status': 'computed'}
        )
        limited = await repository.get_current(COMPANY, {'limit': 1})

        assert [row['value'] for row in by_code_and_period] == ['120.00']
        assert [row['value'] for row in by_code_and_status] == ['40.00']
        assert len(limited) == 1

    async def test_get_current_keeps_both_rows_of_a_real_conflict(
        self, repository: KpiRepositoryPort
    ) -> None:
        await _seed(repository)

        conflicted = await repository.get_current(
            COMPANY,
            {'kpi_codes': ['revenue'], 'period_from': '2025-01-01', 'period_to': '2025-01-31'},
        )

        assert len(conflicted) == 2
        assert {row['value'] for row in conflicted} == {'100.00', '95.00'}
        assert all(row['conflict_marker'] == 'revenue|2025-Q1' for row in conflicted)

    async def test_get_by_company_codes_periods_filters(
        self, repository: KpiRepositoryPort
    ) -> None:
        await _seed(repository)

        margin = await repository.get_by_company_codes_periods(
            COMPANY, ['gross_margin'], '2025-01-01', '2025-03-31'
        )
        later_revenue = await repository.get_by_company_codes_periods(
            COMPANY, ['revenue'], '2025-04-01'
        )
        other_tenant = await repository.get_by_company_codes_periods(OTHER_COMPANY, ['revenue'])

        assert [row['value'] for row in margin] == ['40.00']
        assert [row['value'] for row in later_revenue] == ['120.00']
        assert [row['value'] for row in other_tenant] == ['900.00']

    async def test_get_fingerprint_data_groups_by_chart_and_projects_stable_fields(
        self, repository: KpiRepositoryPort
    ) -> None:
        await _seed(repository)
        specs = [
            {'chart_id': 'revenue-trend', 'kpi_codes': ['revenue']},
            {'chart_id': 'margin-trend', 'kpi_codes': ['gross_margin']},
        ]

        data = await repository.get_fingerprint_data(COMPANY, specs)

        assert set(data) == {'revenue-trend', 'margin-trend'}
        assert len(data['revenue-trend']) == 3
        assert len(data['margin-trend']) == 1
        assert all(set(row) == _FINGERPRINT_FIELDS for rows in data.values() for row in rows)

    async def test_get_fingerprint_data_changes_with_provenance(
        self, repository: KpiRepositoryPort
    ) -> None:
        await _seed(repository)
        specs = [{'chart_id': 'margin-trend', 'kpi_codes': ['gross_margin']}]
        before = await repository.get_fingerprint_data(COMPANY, specs)

        await repository.upsert_batch(
            [_row(kpi_code='gross_margin', period='2025-Q1', value='42.00')]
        )
        after = await repository.get_fingerprint_data(COMPANY, specs)

        assert before['margin-trend'][0]['value'] == '40.00'
        assert after['margin-trend'][0]['value'] == '42.00'
