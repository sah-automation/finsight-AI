"""Unit tests for period and budget KPI computations (issue #375)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from finsight.domain.entities.metric import Metric
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, citation_id, make_metric


def test_dso_divides_receivables_by_revenue_and_multiplies_by_quarter_days() -> None:
    metrics = [
        make_metric('accounts_receivable', Decimal('120.00'), metric_id='ar-1'),
        make_metric('revenue', Decimal('1000.00'), metric_id='rev-1'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_dso(metrics)

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': 'dso',
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': '11.04',
            'source_citations': [citation_id()],
            'source_metric_ids': ['ar-1', 'rev-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
            'reason': None,
        }
    ]


def test_dpo_uses_month_days_for_payables_over_cost_of_goods_sold() -> None:
    metrics = [
        make_metric('accounts_payable', Decimal('62.00'), metric_id='ap-1', period='2026-07'),
        make_metric('cost of goods sold', Decimal('100.00'), metric_id='cogs-1', period='2026-07'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_dpo(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] == '19.22'
    assert rows[0]['period'] == '2026-07'
    assert rows[0]['chart_period'] == '2026-07'
    assert rows[0]['source_metric_ids'] == ['ap-1', 'cogs-1']


@pytest.mark.parametrize(
    ('method', 'metrics', 'expected_reason'),
    [
        (
            'compute_dso',
            [make_metric('accounts_receivable', Decimal('100'), metric_id='ar-1')],
            'missing_revenue',
        ),
        (
            'compute_dpo',
            [make_metric('accounts_payable', Decimal('100'), metric_id='ap-1')],
            'missing_cogs',
        ),
    ],
)
def test_collection_period_kpis_need_review_when_an_input_is_missing(
    method: str, metrics: list[Metric], expected_reason: str
) -> None:
    rows = getattr(KpiComputationService(RULE_VERSION), method)(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


@pytest.mark.parametrize(
    ('method', 'metrics', 'expected_reason'),
    [
        (
            'compute_dso',
            [
                make_metric('accounts_receivable', Decimal('100'), metric_id='ar-1'),
                make_metric('revenue', Decimal('0'), metric_id='rev-1'),
            ],
            'zero_revenue',
        ),
        (
            'compute_dpo',
            [
                make_metric('accounts_payable', Decimal('100'), metric_id='ap-1'),
                make_metric('cogs', Decimal('0'), metric_id='cogs-1'),
            ],
            'zero_cogs',
        ),
    ],
)
def test_collection_period_kpis_need_review_on_zero_denominator(
    method: str, metrics: list[Metric], expected_reason: str
) -> None:
    rows = getattr(KpiComputationService(RULE_VERSION), method)(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


def test_budget_vs_actual_subtracts_budget_from_actual_for_exact_matches() -> None:
    metrics = [
        make_metric('budget', Decimal('410000'), metric_id='budget-1'),
        make_metric('actual', Decimal('416161'), metric_id='actual-1'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_budget_vs_actual(metrics)

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': 'budget_vs_actual',
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': '6161',
            'source_citations': [citation_id()],
            'source_metric_ids': ['budget-1', 'actual-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
            'reason': None,
        }
    ]


@pytest.mark.parametrize(
    ('actual_kwargs', 'expected_reason'),
    [
        ({'period': '2026-Q4'}, 'period_mismatch'),
        ({'currency': 'EUR'}, 'currency_mismatch'),
        ({'units': 'EUR'}, 'units_mismatch'),
    ],
)
def test_budget_vs_actual_needs_review_without_conversion_on_strict_mismatch(
    actual_kwargs: dict[str, str], expected_reason: str
) -> None:
    metrics = [
        make_metric('budget', Decimal('410000'), metric_id='budget-1'),
        make_metric('actual', Decimal('416161'), metric_id='actual-1', **actual_kwargs),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_budget_vs_actual(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


@pytest.mark.parametrize(
    ('metrics', 'expected_reason'),
    [
        ([make_metric('budget', Decimal('410000'), metric_id='budget-1')], 'missing_actual'),
        ([make_metric('actual', Decimal('416161'), metric_id='actual-1')], 'missing_budget'),
    ],
)
def test_budget_vs_actual_needs_review_for_missing_input(
    metrics: list[Metric], expected_reason: str
) -> None:
    rows = KpiComputationService(RULE_VERSION).compute_budget_vs_actual(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


def test_budget_vs_actual_needs_review_without_metric_provenance() -> None:
    budget = Metric(
        metric_id='budget-uncited',
        company_id=COMPANY,
        name='budget',
        value=Decimal('410000'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_version_id='version-uncited',
    )
    actual = make_metric(
        'actual',
        Decimal('416161'),
        metric_id='actual-1',
        version='version-uncited',
    )

    rows = KpiComputationService(RULE_VERSION).compute_budget_vs_actual([budget, actual])

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_citations'


def test_budget_vs_actual_pairs_each_line_item_without_cross_comparing() -> None:
    metrics = [
        make_metric('budget_revenue', Decimal('410000'), metric_id='budget-rev'),
        make_metric('actual_revenue', Decimal('416161'), metric_id='actual-rev'),
        make_metric('budget_cogs', Decimal('240000'), metric_id='budget-cogs'),
        make_metric('actual_cogs', Decimal('250000'), metric_id='actual-cogs'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_budget_vs_actual(metrics)

    assert [(row['source_metric_ids'], row['value']) for row in rows] == [
        (['budget-cogs', 'actual-cogs'], '10000'),
        (['budget-rev', 'actual-rev'], '6161'),
    ]
