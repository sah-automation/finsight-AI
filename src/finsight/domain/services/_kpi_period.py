"""Collection-period KPI computations (DSO/DPO) from Metrics (issue #375).

Both ratios divide a balance-sheet input by a period flow and multiply by the
number of days in the source-declared period. Missing or mismatched inputs stay
``needs_review``; no figure is borrowed from another period or document.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import TYPE_CHECKING, Any

from ._kpi_metric_fields import (
    amount,
    attr,
    code_name,
    exact_sum,
    period_fields,
    required,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.entities.metric import Metric
    from finsight.domain.ports.kpi_repository import KpiRow
    from finsight.domain.services.citation_factory import CitationFactory

_GroupKey = tuple[str, str, str, date]
_Group = dict[str, Any]
_ALIASES = {
    'accounts_receivable': ('accounts_receivable', 'ar', 'receivables'),
    'accounts_payable': ('accounts_payable', 'ap', 'payables'),
    'revenue': ('revenue',),
    'cogs': ('cogs', 'cost_of_goods_sold'),
}


def compute_collection_period(
    *,
    kpi_code: str,
    numerator_code: str,
    denominator_code: str,
    metrics: Sequence[Metric],
    rule_version: str,
    citations: CitationFactory,
) -> list[KpiRow]:
    """Build one DSO/DPO row per company, source period and document version."""
    numerators = _input_groups(metrics, numerator_code, citations)
    denominators = _input_groups(metrics, denominator_code, citations)
    rows: list[KpiRow] = []
    for key in sorted(set(numerators) | set(denominators)):
        numerator, denominator = numerators.get(key), denominators.get(key)
        reason = _reason(numerator_code, numerator, denominator_code, denominator)
        if reason is None and denominator is not None and _total(denominator) == 0:
            reason = f'zero_{denominator_code}'
        value = _value(key, numerator, denominator, reason)
        rows.append(_row(kpi_code, key, (numerator, denominator), value, reason, rule_version))
    return rows


def _value(
    key: _GroupKey,
    numerator: _Group | None,
    denominator: _Group | None,
    reason: str | None,
) -> str | None:
    if reason or numerator is None or denominator is None:
        return None
    with localcontext() as context:
        context.prec = 34
        days = Decimal(_days_in_period(key[1]))
        return str(
            (_total(numerator) / _total(denominator) * days).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        )


def _reason(
    numerator_code: str,
    numerator: _Group | None,
    denominator_code: str,
    denominator: _Group | None,
) -> str | None:
    if numerator is None:
        return f'missing_{numerator_code}'
    if denominator is None:
        return f'missing_{denominator_code}'
    present = (numerator, denominator)
    missing = {field for group in present for field in group['missing_fields']}
    if 'currency' in missing:
        return 'missing_currency'
    if 'units' in missing:
        return 'missing_units'
    if len({value for group in present for value in group['currencies']}) > 1:
        return 'currency_mismatch'
    if len({value for group in present for value in group['unit_values']}) > 1:
        return 'units_mismatch'
    if any(group['missing_citation'] for group in present):
        return 'missing_citations'
    return None


def _matches(metric: Metric, code: str) -> bool:
    aliases = {code_name(alias) for alias in _ALIASES[code]}
    for field in ('kpi_code', 'name', 'metric_name', 'metric', 'label'):
        value = attr(metric, field)
        if value is not None and code_name(value) in aliases:
            return True
    return False


def _input_groups(
    metrics: Sequence[Metric], code: str, citations: CitationFactory
) -> dict[_GroupKey, _Group]:
    groups: dict[_GroupKey, _Group] = {}
    for metric in metrics or ():
        if metric is None or not _matches(metric, code):
            continue
        label, start = period_fields(metric)
        company = required(metric, 'company_id', 'company_id', 'company', 'tenant_id')
        version = required(
            metric, 'document_version_id', 'document_version_id', 'document_version', 'version_id'
        )
        group = groups.setdefault((company, label, version, start), _new_group(metric))
        _add_metric(group, metric, citations)
    return groups


def _new_group(metric: Metric) -> _Group:
    group = _blank_group()
    group['currency'] = _field(metric, 'currency')
    group['units'] = _field(metric, 'units', 'unit')
    return group


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


def _add_metric(group: _Group, metric: Metric, citations: CitationFactory) -> None:
    currency, units = _field(metric, 'currency'), _field(metric, 'units', 'unit')
    for value, field, values in (
        (currency, 'currency', 'currencies'),
        (units, 'units', 'unit_values'),
    ):
        if value:
            group[values].add(value)
        else:
            group['missing_fields'].add(field)
    group['amounts'].append(amount(metric))
    metric_id = required(metric, 'metric_id', 'metric_id', 'id')
    if metric_id not in group['metric_ids']:
        group['metric_ids'].append(metric_id)
    citation = citations.build_from_metric(metric)
    if citation:
        group['citations'].add(citation)
    else:
        group['missing_citation'] = True


def _field(metric: Metric, *names: str) -> str:
    value = attr(metric, *names)
    return '' if value is None else str(value).strip()


def _total(group: _Group) -> Decimal:
    return exact_sum(group['amounts'])


def _days_in_period(label: str) -> int:
    quarter = re.fullmatch(r'(\d{4})-(Q[1-4])', label, re.IGNORECASE)
    if quarter:
        year, number = int(quarter.group(1)), int(quarter.group(2)[1])
        first_month = 3 * (number - 1) + 1
        return sum(
            calendar.monthrange(year, month)[1] for month in range(first_month, first_month + 3)
        )
    month = re.fullmatch(r'(\d{4})-(\d{2})', label)
    if month:
        return calendar.monthrange(int(month.group(1)), int(month.group(2)))[1]
    try:
        day = date.fromisoformat(label)
    except ValueError:
        raise ValueError(f'Unsupported KPI period label: {label!r}') from None
    return calendar.monthrange(day.year, day.month)[1]


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
    source = next((group for group in present if group['currency']), _blank_group())
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
        'currency': source['currency'],
        'units': source['units'],
        'value': value,
        'source_citations': sorted(
            {citation for group in present for citation in group['citations']}
        ),
        'source_metric_ids': metric_ids,
        'computation_status': 'needs_review' if reason else 'computed',
        'estimation_method': None,
        'document_version_id': version,
        'computation_rule_version': rule_version,
        'superseded_by_document_version_id': None,
        'reason': reason,
    }


__all__ = ['compute_collection_period']
