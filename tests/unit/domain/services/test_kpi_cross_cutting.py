"""Unit tests for cross-cutting KPI row logic (issue #375)."""

from __future__ import annotations

from decimal import Decimal

from finsight.domain.services.kpi_computation_service import KpiComputationService
from finsight.domain.value_objects.computation_status import ComputationStatus
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


def test_quarterly_spread_rounds_equal_shares_consistently() -> None:
    row = KpiComputationService(RULE_VERSION).compute_revenue(
        [make_metric('revenue', Decimal('100.00'), metric_id='rev-1')]
    )[0]

    rows = KpiComputationService(RULE_VERSION).spread_quarterly([row])

    assert [monthly['value'] for monthly in rows] == ['33.33', '33.33', '33.34']


def test_quarterly_spread_leaves_non_quarterly_rows_untouched() -> None:
    row = KpiComputationService(RULE_VERSION).compute_revenue(
        [make_metric('revenue', Decimal('100.00'), metric_id='rev-1', period='2026-07')]
    )[0]

    assert KpiComputationService(RULE_VERSION).spread_quarterly([row]) == [row]


def _computed_row(*, version: str, value: str, period: str = '2026-Q3') -> dict[str, object]:
    return KpiComputationService(RULE_VERSION).compute_revenue(
        [
            make_metric(
                'revenue',
                Decimal(value),
                metric_id=f'rev-{version}',
                version=version,
                period=period,
            )
        ]
    )[0]


def test_cross_document_conflict_keeps_both_computed_rows_with_markers() -> None:
    older = _computed_row(version='version-1', value='100.00')
    newer = _computed_row(version='version-2', value='120.00')

    rows = KpiComputationService(RULE_VERSION).mark_conflicts([older, newer])

    assert len(rows) == 2
    assert [row['computation_status'] for row in rows] == [ComputationStatus.COMPUTED] * 2
    assert [row['conflict_marker'] for row in rows] == ['revenue|2026-Q3'] * 2
    assert [row['value'] for row in rows] == ['100.00', '120.00']
    assert [row['source_citations'] for row in rows] == [
        ['cit:v1:version-1:p1'],
        ['cit:v1:version-2:p1'],
    ]


def test_conflict_requires_different_figures_not_just_different_versions() -> None:
    older = _computed_row(version='version-1', value='100')
    newer = _computed_row(version='version-2', value='100.00')

    rows = KpiComputationService(RULE_VERSION).mark_conflicts([older, newer])

    assert [row.get('conflict_marker') for row in rows] == [None, None]


def test_conflict_uses_declared_period_across_estimated_chart_months() -> None:
    service = KpiComputationService(RULE_VERSION)
    older = service.spread_quarterly([_computed_row(version='version-1', value='100.00')])[0]
    newer = service.spread_quarterly([_computed_row(version='version-2', value='120.00')])[1]

    rows = service.mark_conflicts([older, newer])

    assert [row['conflict_marker'] for row in rows] == ['revenue|2026-Q3'] * 2


def test_same_document_rows_are_not_marked_as_conflicts() -> None:
    first = _computed_row(version='version-1', value='100.00')
    second = _computed_row(version='version-1', value='120.00')

    rows = KpiComputationService(RULE_VERSION).mark_conflicts([first, second])

    assert [row.get('conflict_marker') for row in rows] == [None, None]


def test_superseded_rows_point_to_newer_version_from_same_document_history() -> None:
    older = _computed_row(version='version-1', value='100.00')
    current = _computed_row(version='version-2', value='120.00')

    rows = KpiComputationService(RULE_VERSION).mark_supersession(
        [older, current], {'version-1': 'version-2'}
    )

    assert rows[0]['superseded_by_document_version_id'] == 'version-2'
    assert rows[1]['superseded_by_document_version_id'] is None


def test_superseded_history_is_not_reported_as_a_conflict() -> None:
    older = _computed_row(version='version-1', value='100.00')
    current = _computed_row(version='version-2', value='120.00')
    service = KpiComputationService(RULE_VERSION)
    history = service.mark_supersession([older, current], {'version-1': 'version-2'})

    rows = service.mark_conflicts(history)

    assert [row.get('conflict_marker') for row in rows] == [None, None]


def test_display_label_precedence_is_updating_then_estimated_then_draft() -> None:
    service = KpiComputationService(RULE_VERSION)
    computed = _computed_row(version='version-1', value='900.00')
    estimated = service.spread_quarterly([computed])[0]
    statuses = {'version-1': 'draft'}

    updating = service.apply_display_labels([estimated], document_statuses=statuses, updating=True)
    no_updating = service.apply_display_labels([estimated], document_statuses=statuses)

    assert updating[0]['display_label'] == 'Updating'
    assert no_updating[0]['display_label'] == 'Estimated'


def test_draft_display_label_comes_from_source_document_status() -> None:
    row = _computed_row(version='version-1', value='100.00')

    rows = KpiComputationService(RULE_VERSION).apply_display_labels(
        [row], document_statuses={'version-1': 'draft'}
    )

    assert rows[0]['display_label'] == 'Draft'


def test_final_and_unmarked_rows_have_no_display_label() -> None:
    row = _computed_row(version='version-1', value='100.00')

    rows = KpiComputationService(RULE_VERSION).apply_display_labels(
        [row], document_statuses={'version-1': 'final'}
    )

    assert rows[0]['display_label'] is None


def test_updating_label_can_be_scoped_to_kpi_codes() -> None:
    revenue = _computed_row(version='version-1', value='100.00')
    dso = dict(revenue, kpi_code='dso')

    rows = KpiComputationService(RULE_VERSION).apply_display_labels(
        [revenue, dso], updating={'dso'}
    )

    assert [row['display_label'] for row in rows] == [None, 'Updating']
