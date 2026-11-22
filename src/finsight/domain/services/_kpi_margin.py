"""Margin percentage computations shared by KPI service methods (issue #373).

Gross and net margins are code-computed from Metrics: no model maths, no
currency or unit conversion, and no borrowing figures from another period or
document version. A margin row keeps the provenance of both input Metrics.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any

from ._kpi_metric_fields import amount, exact_sum, matches_code, period_fields, required

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.entities.metric import Metric
    from finsight.domain.ports.kpi_repository import KpiRow
    from finsight.domain.services.citation_factory import CitationFactory

_GroupKey = tuple[str, str, str, date]


def compute_margin(
    *,
    kpi_code: str,
    input_code: str,
    metrics: Sequence[Metric],
    rule_version: str,
    citations: CitationFactory,
) -> list[KpiRow]:
    """Build one margin row per company, period and document version."""
    revenue = _input_groups(metrics, 'revenue', citations)
    inputs = _input_groups(metrics, input_code, citations)
    rows: list[KpiRow] = []
    for key in sorted(set(revenue) | set(inputs)):
        revenue_group = revenue.get(key)
        input_group = inputs.get(key)
        if revenue_group is None or input_group is None:
            continue
        value = _percentage(_total(revenue_group), _total(input_group))
        rows.append(_row(kpi_code, key, revenue_group, input_group, value, None, rule_version))
    return rows


def _input_groups(
    metrics: Sequence[Metric], code: str, citations: CitationFactory
) -> dict[_GroupKey, dict[str, Any]]:
    groups: dict[_GroupKey, dict[str, Any]] = {}
    for metric in metrics or ():
        if metric is None or not matches_code(metric, code):
            continue
        label, start = period_fields(metric)
        company = required(metric, 'company_id', 'company_id', 'company', 'tenant_id')
        version = required(
            metric, 'document_version_id', 'document_version_id', 'document_version', 'version_id'
        )
        key = (company, label, version, start)
        group = groups.setdefault(key, _new_group(metric))
        group['amounts'].append(amount(metric))
        metric_id = required(metric, 'metric_id', 'metric_id', 'id')
        if metric_id not in group['metric_ids']:
            group['metric_ids'].append(metric_id)
        citation = citations.build_from_metric(metric)
        if citation:
            group['citations'].add(citation)
        else:
            group['missing_citation'] = True
    return groups


def _new_group(metric: Metric) -> dict[str, Any]:
    return {
        'currency': required(metric, 'currency', 'currency'),
        'units': required(metric, 'units', 'unit', 'units'),
        'amounts': [],
        'metric_ids': [],
        'citations': set(),
        'missing_citation': False,
    }


def _total(group: dict[str, Any]) -> Decimal:
    return exact_sum(group['amounts'])


def _percentage(revenue: Decimal, input_amount: Decimal) -> str:
    with localcontext() as context:
        context.prec = 34
        return str((revenue - input_amount) / revenue * Decimal('100'))


def _row(
    kpi_code: str,
    key: _GroupKey,
    revenue: dict[str, Any],
    inputs: dict[str, Any],
    value: str | None,
    reason: str | None,
    rule_version: str,
) -> KpiRow:
    company, label, version, start = key
    citations = sorted(revenue['citations'] | inputs['citations'])
    status = 'needs_review' if reason else 'computed'
    return {
        'company_id': company,
        'kpi_code': kpi_code,
        'period': label,
        'period_start': start.isoformat(),
        'chart_period': label,
        'chart_period_start': start.isoformat(),
        'currency': revenue['currency'],
        'units': revenue['units'],
        'value': value,
        'source_citations': citations,
        'source_metric_ids': revenue['metric_ids']
        + [ident for ident in inputs['metric_ids'] if ident not in revenue['metric_ids']],
        'computation_status': status,
        'estimation_method': None,
        'document_version_id': version,
        'computation_rule_version': rule_version,
        'superseded_by_document_version_id': None,
        'reason': reason,
    }


__all__ = ['compute_margin']
