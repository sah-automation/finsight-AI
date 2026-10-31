"""Math helper functions for :class:`Calculator`."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if hasattr(value, 'value'):
        return _to_decimal(value.value)
    text = str(value).strip().replace(',', '')
    cleaned = ''.join(ch for ch in text if ch.isdigit() or ch in '.-')
    if not cleaned or cleaned in {'.', '-', '-.'}:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _attr(obj: object, *names: str) -> object:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return None
    for name in names:
        if hasattr(obj, name):
            v = getattr(obj, name)
            if v is not None:
                return v
    return None


def _value_from_metric(metric: object) -> object:
    if isinstance(metric, dict):
        for key in ('value', 'amount', 'figure', 'metric_value', 'result'):
            if key in metric and metric[key] is not None:
                return metric[key]
        return None
    for attr in ('value', 'amount', 'figure', 'metric_value', 'result'):
        if hasattr(metric, attr):
            v = getattr(metric, attr)
            if v is not None:
                return v
    return metric


def _metric_id(metric: object) -> str:
    mid = _attr(metric, 'metric_id', 'id', 'metricId', 'metricID', 'uuid')
    if mid is not None:
        return str(mid)
    return str(metric)


def _scope_value(metric: object, *names: str) -> object:
    return _attr(metric, *names)
