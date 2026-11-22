"""Unit tests for cross-cutting KPI row logic (issue #375)."""

from __future__ import annotations

from decimal import Decimal

from finsight.domain.value_objects.computation_status import ComputationStatus

from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import RULE_VERSION, make_metric


def test_quarterly_spread_keeps_declared_period_and_estimates_each_month() -> None:
    row = KpiComputationService(RULE_VERSION).compute_revenue(
        [make_metric('revenue', Decimal('900.00'), metric_id='rev-1')]
    )[0]

    rows = KpiComputationService(RULE_VERSION).spread_quarterly([row])

    assert len(rows) == 3
    assert [
        (r['period'], r['chart_period'], r['chart_period_start'], r['value']) for r in rows
    ] == [
        ('2026-Q3', '2026-07', '2026-07-01', '300.00'),
        ('2026-Q3', '2026-08', '2026-08-01', '300.00'),
        ('2026-Q3', '2026-09', '2026-09-01', '300.00'),
    ]
    assert all(r['computation_status'] == ComputationStatus.ESTIMATED for r in rows)
    assert all(r['estimation_method'] == 'quarterly_spread_equal' for r in rows)
    assert all(r['display_label'] == 'Estimated' for r in rows)
    assert all(r['source_metric_ids'] == ['rev-1'] for r in rows)


def test_quarterly_spread_leaves_non_quarterly_rows_untouched() -> None:
    row = KpiComputationService(RULE_VERSION).compute_revenue(
        [make_metric('revenue', Decimal('100.00'), metric_id='rev-1', period='2026-07')]
    )[0]

    assert KpiComputationService(RULE_VERSION).spread_quarterly([row]) == [row]
