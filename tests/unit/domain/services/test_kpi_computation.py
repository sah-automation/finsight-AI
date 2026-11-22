"""Unit tests for the pure core KPI aggregation service (issue #372)."""

from __future__ import annotations

from decimal import Decimal

from finsight.domain.services.kpi_computation import KpiComputationService

from finsight.core.types import CompanyId
from finsight.domain.entities.metric import Metric

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
RULE_VERSION = 'rule-v1'


def test_compute_revenue_emits_one_computed_row_with_exact_decimal_string() -> None:
    metric = Metric(
        metric_id='metric-revenue-1',
        company_id=COMPANY,
        name='revenue',
        value=Decimal('1234.50'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='version-1',
    )

    rows = KpiComputationService(RULE_VERSION).compute_revenue([metric])

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': 'revenue',
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': '1234.50',
            'source_citations': ['metric-revenue-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
        }
    ]
