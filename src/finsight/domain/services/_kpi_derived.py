"""Derived burn-rate and runway KPI computations (issue #374).

Burn rate and runway are computed in pure code from Metrics for one company,
period and document version. Missing, mismatched or uncited inputs produce a
needs_review row with no guessed value.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import TYPE_CHECKING, Any

from ._kpi_metric_fields import amount, attr, exact_sum, matches_code, period_fields, required

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.entities.metric import Metric
    from finsight.domain.ports.kpi_repository import KpiRow
    from finsight.domain.services.citation_factory import CitationFactory

_GroupKey = tuple[str, str, str, date]
_Group = dict[str, Any]


def compute_burn_rate(
    *,
    metrics: Sequence[Metric],
    rule_version: str,
    citations: CitationFactory,
) -> list[KpiRow]:
    """Build one burn-rate row per company, period and document version."""
    expenses = _input_groups(metrics, 'operating_expenses', citations)
    flows = _input_groups(metrics, 'cash_flow', citations)
    rows: list[KpiRow] = []
    for key in sorted(set(expenses) | set(flows)):
        expense, flow = expenses.get(key), flows.get(key)
        reason = _reason(('operating_expenses', 'cash_flow'), (expense, flow))
        if reason or expense is None or flow is None:
            value = None
        else:
            value = str(_total(expense) - _total(flow))
        rows.append(_row('burn_rate', key, (expense, flow), value, reason, rule_version))
    return rows


def compute_runway(
    *,
    metrics: Sequence[Metric],
    rule_version: str,
    citations: CitationFactory,
) -> list[KpiRow]:
    """Build one runway row per company, period and document version."""
    cash = _input_groups(metrics, 'cash', citations)
    expenses = _input_groups(metrics, 'operating_expenses', citations)
    flows = _input_groups(metrics, 'cash_flow', citations)
    rows: list[KpiRow] = []
    for key in sorted(set(cash) | set(expenses) | set(flows)):
        cash_group, expense, flow = cash.get(key), expenses.get(key), flows.get(key)
        groups = (cash_group, expense, flow)
        reason = _reason(('cash', 'operating_expenses', 'cash_flow'), groups)
        if reason or cash_group is None or expense is None or flow is None:
            value = None
        else:
            burn = _total(expense) - _total(flow)
            if burn == 0:
                reason = 'zero_burn_rate'
                value = None
            else:
                value = _months(_total(cash_group), burn)
        rows.append(_row('runway', key, groups, value, reason, rule_version))
    return rows


def _reason(codes: tuple[str, ...], groups: tuple[_Group | None, ...]) -> str | None:
    """Return the first reason a derived KPI cannot be computed."""
    for code, group in zip(codes, groups, strict=True):
        if group is None:
            return f'missing_{code}'
    present = [group for group in groups if group is not None]
    missing_fields = {field for group in present for field in group['missing_fields']}
    if 'currency' in missing_fields:
        return 'missing_currency'
    if 'units' in missing_fields:
        return 'missing_units'
    currencies = {value for group in present for value in group['currencies']}
    if len(currencies) > 1:
        return 'currency_mismatch'
    unit_values = {value for group in present for value in group['unit_values']}
    if len(unit_values) > 1:
        return 'units_mismatch'
    if any(group['missing_citation'] for group in present):
        return 'missing_citations'
    return None


def _blank_group() -> _Group:
    return {
        'currency': '',
        'units': '',
        'currencies': set(),
        'unit_values': set(),
        'amounts': [],
        'metric_ids': [],
        'citations': set(),
        'missing_citation': False,
        'missing_fields': set(),
    }


def _input_groups(
    metrics: Sequence[Metric], code: str, citations: CitationFactory
) -> dict[_GroupKey, _Group]:
    groups: dict[_GroupKey, _Group] = {}
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
        _add_metric(group, metric, citations)
    return groups


def _new_group(metric: Metric) -> _Group:
    group = _blank_group()
    group['currency'] = _field(metric, 'currency')
    group['units'] = _field(metric, 'units', 'unit')
    return group


def _add_metric(group: _Group, metric: Metric, citations: CitationFactory) -> None:
    currency, units = _field(metric, 'currency'), _field(metric, 'units', 'unit')
    _track_dimensions(group, currency, units)
    group['amounts'].append(amount(metric))
    metric_id = required(metric, 'metric_id', 'metric_id', 'id')
    if metric_id not in group['metric_ids']:
        group['metric_ids'].append(metric_id)
    citation = citations.build_from_metric(metric)
    if citation:
        group['citations'].add(citation)
    else:
        group['missing_citation'] = True


def _track_dimensions(group: _Group, currency: str, units: str) -> None:
    if currency:
        group['currencies'].add(currency)
    else:
        group['missing_fields'].add('currency')
    if units:
        group['unit_values'].add(units)
    else:
        group['missing_fields'].add('units')


def _field(metric: Metric, *names: str) -> str:
    value = attr(metric, *names)
    return '' if value is None else str(value).strip()


def _total(group: _Group) -> Decimal:
    return exact_sum(group['amounts'])


def _months(cash: Decimal, burn: Decimal) -> str:
    with localcontext() as context:
        context.prec = 34
        months = cash / burn
        return str(months.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _row(
    kpi_code: str,
    key: _GroupKey,
    groups: tuple[_Group | None, ...],
    value: str | None,
    reason: str | None,
    rule_version: str,
) -> KpiRow:
    company, label, version, start = key
    present = [group for group in groups if group is not None]
    dimension_source = next((group for group in present if group['currency']), _blank_group())
    citations = sorted({citation for group in present for citation in group['citations']})
    metric_ids: list[str] = []
    for group in present:
        for ident in group['metric_ids']:
            if ident not in metric_ids:
                metric_ids.append(ident)
    return {
        'company_id': company,
        'kpi_code': kpi_code,
        'period': label,
        'period_start': start.isoformat(),
        'chart_period': label,
        'chart_period_start': start.isoformat(),
        'currency': dimension_source['currency'],
        'units': dimension_source['units'],
        'value': value,
        'source_citations': citations,
        'source_metric_ids': metric_ids,
        'computation_status': 'needs_review' if reason else 'computed',
        'estimation_method': None,
        'document_version_id': version,
        'computation_rule_version': rule_version,
        'superseded_by_document_version_id': None,
        'reason': reason,
    }


__all__ = ['compute_burn_rate', 'compute_runway']
