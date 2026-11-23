"""Unit tests for resolving chart variance inputs from source metrics (issue #380)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.chart_variance_resolver import ChartVarianceResolver

pytestmark = pytest.mark.unit

COMPANY = '7e1a0000-0000-4000-8000-000000000001'
VERSION = '10000000-0000-4000-8000-000000000003'


class _MetricRepository:
    def __init__(self, metrics: list[Any]) -> None:
        self.metrics = metrics
        self.calls: list[dict[str, Any]] = []

    async def list_metrics(self, company_id: str, **filters: Any) -> list[Any]:
        self.calls.append({'company_id': company_id, **filters})
        return list(self.metrics)


def _metric(metric_id: str, name: str, value: str) -> Any:
    return SimpleNamespace(
        metric_id=metric_id,
        name=name,
        value=value,
        version_id=VERSION,
        currency='USD',
        units='USD',
        period='2025-Q1',
        company_id=COMPANY,
    )


def _variance_row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'kpi_code': 'budget_vs_actual',
        'value': '20.00',
        'period': '2025-Q1',
        'chart_period': '2025-Q1',
        'document_version_id': VERSION,
        'source_metric_ids': ['budget-1', 'actual-1'],
        'source_citations': [],
        'computation_status': 'computed',
    }
    row.update(extra)
    return row


@pytest.mark.asyncio
async def test_variance_totals_come_from_source_metrics() -> None:
    repository = _MetricRepository(
        [
            _metric('budget-1', 'budget_revenue', '100.00'),
            _metric('actual-1', 'actual_revenue', '120.00'),
            _metric('other-1', 'revenue', '999.00'),
        ]
    )

    enriched = await ChartVarianceResolver(repository).enrich(
        COMPANY, [_variance_row()], ['budget_vs_actual']
    )

    assert enriched[0]['actual'] == '120.00'
    assert enriched[0]['budget'] == '100.00'
    assert enriched[0]['name'] == 'revenue'
    assert repository.calls == [{'company_id': COMPANY, 'version_ids': [VERSION]}]


@pytest.mark.asyncio
async def test_unrelated_rows_are_not_fetched_or_changed() -> None:
    repository = _MetricRepository([])
    revenue_row = {'kpi_code': 'revenue', 'value': '10.00'}

    enriched = await ChartVarianceResolver(repository).enrich(
        COMPANY, [revenue_row], ['budget_vs_actual']
    )

    assert enriched == [revenue_row]
    assert repository.calls == []


@pytest.mark.asyncio
async def test_explicit_totals_are_preserved() -> None:
    repository = _MetricRepository([])
    row = _variance_row(actual='5.00', budget='3.00', name='Legacy')

    enriched = await ChartVarianceResolver(repository).enrich(COMPANY, [row], ['budget_vs_actual'])

    assert enriched == [row]
    assert repository.calls == []
