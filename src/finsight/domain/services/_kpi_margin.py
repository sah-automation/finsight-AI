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
_MISSING_INPUT_REASON = {'cogs': 'missing_cogs', 'net_income': 'missing_net_income'}


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
        rows.append(
            _group_row(kpi_code, key, revenue.get(key), inputs.get(key), input_code, rule_version)
        )
    return rows


def _group_row(
    kpi_code: str,
    key: _GroupKey,
    revenue_group: dict[str, Any] | None,
    input_group: dict[str, Any] | None,
    input_code: str,
    rule_version: str,
) -> KpiRow:
    reason = _reason(revenue_group, input_group, input_code)
    if reason or revenue_group is None or input_group is None:
        value = None
    else:
        value = _percentage(_total(revenue_group), _total(input_group))
    return _row(
        kpi_code,
        key,
        revenue_group or _blank_group(),
        input_group or _blank_group(),
        value,
        reason,
        rule_version,
    )


def _reason(
    revenue: dict[str, Any] | None, inputs: dict[str, Any] | None, input_code: str
) -> str | None:
    if revenue is None:
        return 'missing_revenue'
    if inputs is None:
        return _MISSING_INPUT_REASON.get(input_code, f'missing_{input_code}')
    if len(revenue['currencies'] | inputs['currencies']) > 1:
        return 'currency_mismatch'
    if len(revenue['unit_values'] | inputs['unit_values']) > 1:
        return 'units_mismatch'
    return None


def _blank_group() -> dict[str, Any]:
    return {
        'currency': '',
        'units': '',
        'currencies': set(),
        'unit_values': set(),
        'amounts': [],
        'metric_ids': [],
        'citations': set(),
        'missing_citation': False,
    }


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
        group['currencies'].add(required(metric, 'currency', 'currency'))
        group['unit_values'].add(required(metric, 'units', 'unit', 'units'))
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
    group = _blank_group()
    currency = required(metric, 'currency', 'currency')
    units = required(metric, 'units', 'unit', 'units')
    group['currency'] = currency
    group['units'] = units
    group['currencies'].add(currency)
    group['unit_values'].add(units)
    return group


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
    source = revenue if revenue['currency'] else inputs
    citations = sorted(revenue['citations'] | inputs['citations'])
    status = 'needs_review' if reason else 'computed'
    return {
        'company_id': company,
        'kpi_code': kpi_code,
        'period': label,
        'period_start': start.isoformat(),
        'chart_period': label,
        'chart_period_start': start.isoformat(),
        'currency': source['currency'],
        'units': source['units'],
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
