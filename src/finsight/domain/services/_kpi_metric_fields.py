"""Shared field readers for Metrics used by KPI computation services.

These helpers keep KPI services free of I/O and vendor imports. They accept
either a ``Metric`` entity or a mapping so callers can use the same rules for
stored rows and freshly extracted figures.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from finsight.domain.entities.metric import Metric

_QUARTER_START_MONTHS = (1, 4, 7, 10)


def attr(value: Any, *names: str) -> Any:
    """Read the first present field from a mapping or an object."""
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None
    for name in names:
        found = getattr(value, name, None)
        if found is not None:
            return found
    return None


def code_name(value: Any) -> str:
    """Normalise a metric code or name for comparison."""
    text = '' if value is None else str(value).strip().lower()
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def matches_code(metric: Metric, kpi_code: str) -> bool:
    """Check a Metric against a KPI code, honouring an explicit kpi_code."""
    explicit = attr(metric, 'kpi_code')
    if explicit is not None:
        return code_name(explicit) == kpi_code
    for field in ('name', 'metric_name', 'metric', 'label'):
        name = attr(metric, field)
        if name is not None:
            return code_name(name) == kpi_code
    return False


def period_start(period: Any) -> date:
    """Derive a start date from a declared period label."""
    start = getattr(period, 'start_date', None)
    if isinstance(start, date):
        return start
    label = '' if period is None else str(period).strip()
    try:
        return date.fromisoformat(label)
    except ValueError:
        pass
    match = re.fullmatch(r'(\d{4})-(Q[1-4])', label, re.IGNORECASE)
    if match:
        quarter = int(match.group(2)[1])
        return date(int(match.group(1)), _QUARTER_START_MONTHS[quarter - 1], 1)
    match = re.fullmatch(r'(\d{4})-(\d{2})', label)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    raise ValueError(f'Unsupported KPI period label: {label!r}')


def period_fields(metric: Metric) -> tuple[str, date]:
    """Return the declared period label and its derived start date."""
    period_attr = attr(metric, 'period', 'fiscal_period', 'reporting_period')
    start = period_start(period_attr)
    label = period_attr if isinstance(period_attr, str) else getattr(period_attr, 'label', None)
    text = start.isoformat() if label is None else str(label).strip()
    return text, start


def required(metric: Metric, field: str, *names: str) -> str:
    """Return a required non-empty field or fail with a clear message."""
    value = attr(metric, *names)
    text = '' if value is None else str(value).strip()
    if not text:
        raise ValueError(f'KPI Metrics require {field}')
    return text


def amount(metric: Metric) -> Decimal:
    """Convert a Metric figure to an exact, finite Decimal."""
    value = attr(metric, 'value', 'amount', 'figure')
    if isinstance(value, (bool, float)):
        raise TypeError('KPI Metric values must be Decimal, int or str, never float')
    try:
        figure = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'Invalid KPI Metric value: {value!r}') from None
    if not figure.is_finite():
        raise ValueError(f'KPI Metric value must be finite: {value!r}')
    return figure


def exact_sum(values: list[Decimal]) -> Decimal:
    """Add exact decimals without letting the ambient context round them."""
    if not values:
        return Decimal('0')
    highest = max(value.adjusted() for value in values)
    lowest = min(cast('int', value.as_tuple().exponent) for value in values)
    required_precision = max(highest - lowest + 1, 1)
    with localcontext() as context:
        context.prec = max(context.prec, required_precision)
        return sum(values, Decimal('0'))


__all__ = [
    'amount',
    'attr',
    'code_name',
    'exact_sum',
    'matches_code',
    'period_fields',
    'required',
]
