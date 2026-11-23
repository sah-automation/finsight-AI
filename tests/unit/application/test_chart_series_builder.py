"""Unit tests for the chart series computation seam (issue #380).

Derived figures are checked against hand-worked decimal examples so the
assertions do not repeat the implementation's arithmetic.
"""

from __future__ import annotations

from typing import Any

import pytest

from finsight.application.chart_series_builder import ChartSeriesBuilder

pytestmark = pytest.mark.unit

VERSION = '10000000-0000-4000-8000-000000000001'


def _row(
    value: str | None,
    *,
    period: str = '2025-Q1',
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        'kpi_code': 'revenue',
        'period': period,
        'chart_period': period,
        'chart_period_start': f'{period[:4]}-{(int(period[-1]) - 1) * 3 + 1:02d}-01',
        'currency': 'USD',
        'units': 'USD',
        'value': value,
        'source_citations': [f'cit:v1:{VERSION}:p1'],
        'computation_status': 'computed',
        'document_version_id': VERSION,
    }
    row.update(extra)
    return row


def _build(
    rows: list[dict[str, Any]],
    *,
    polarity: str = 'higher_is_better',
    variance_kpi_codes: list[str] | None = None,
    kpi_codes: list[str] | None = None,
) -> dict[str, Any]:
    return ChartSeriesBuilder().build(
        rows,
        kpi_codes=kpi_codes or ['revenue'],
        polarity=polarity,
        variance_kpi_codes=variance_kpi_codes or [],
    )


def test_change_and_direction_follow_configured_polarity() -> None:
    rows = [_row('100.00'), _row('150.00', period='2025-Q2')]

    higher = _build(rows)
    lower = _build(rows, polarity='lower_is_better')
    neutral = _build(rows, polarity='neutral')

    assert higher['labels'] == ['2025-Q1', '2025-Q2']
    points = higher['datasets'][0]['points']
    assert points[0]['change'] is None
    assert points[0]['change_direction'] is None
    assert points[1]['change'] == '50.00'
    assert points[1]['change_direction'] == 'good'
    assert lower['datasets'][0]['points'][1]['change_direction'] == 'bad'
    assert neutral['datasets'][0]['points'][1]['change_direction'] is None


def test_share_is_percentage_of_the_dataset_total() -> None:
    result = _build([_row('100.00'), _row('300.00', period='2025-Q2')])

    points = result['datasets'][0]['points']
    assert [point['share'] for point in points] == ['25.00', '75.00']
    assert result['datasets'][0]['data'] == ['100.00', '300.00']


def test_null_value_is_a_point_reason_and_not_a_guessed_number() -> None:
    rows = [_row(None, computation_status='needs_review')]

    result = _build(rows)
    point = result['datasets'][0]['points'][0]

    assert result['datasets'][0]['data'] == [None]
    assert point['value'] is None
    assert point['computation_status'] == 'needs_review'
    assert point['reason'] == 'insufficient_data'


def test_variance_rows_use_explicit_actual_and_budget() -> None:
    rows = [
        _row(
            '20.00',
            kpi_code='budget_vs_actual',
            name='Revenue',
            actual='120.00',
            budget='100.00',
        )
    ]

    variance_codes = ['budget_vs_actual']
    favourable = _build(rows, variance_kpi_codes=variance_codes, kpi_codes=variance_codes)
    unfavourable = _build(
        rows,
        polarity='lower_is_better',
        variance_kpi_codes=variance_codes,
        kpi_codes=variance_codes,
    )

    assert favourable['variance_rows'] == [
        {
            'name': 'Revenue',
            'actual': '120.00',
            'budget': '100.00',
            'variance': '20.00',
            'favourable': True,
        }
    ]
    assert unfavourable['variance_rows'][0]['favourable'] is False


def test_variance_falls_back_to_the_kpi_value_and_neutral_polarity() -> None:
    rows = [_row('-5.00', kpi_code='budget_vs_actual', period='2025-Q1')]

    variance_codes = ['budget_vs_actual']
    result = _build(
        rows,
        polarity='neutral',
        variance_kpi_codes=variance_codes,
        kpi_codes=variance_codes,
    )

    assert result['variance_rows'][0]['actual'] is None
    assert result['variance_rows'][0]['budget'] is None
    assert result['variance_rows'][0]['variance'] == '-5.00'
    assert result['variance_rows'][0]['favourable'] is False


def test_variance_rows_follow_the_configured_kpi_codes() -> None:
    rows = [_row('5.00', kpi_code='configured_variance', actual='10.00', budget='5.00')]

    result = _build(
        rows,
        variance_kpi_codes=['configured_variance'],
        kpi_codes=['configured_variance'],
    )

    assert result['variance_rows'][0]['variance'] == '5.00'


def test_empty_rows_return_the_insufficient_data_envelope() -> None:
    result = _build([])

    assert result == {
        'labels': [],
        'datasets': [],
        'variance_rows': [],
        'reason': 'insufficient_data',
    }
