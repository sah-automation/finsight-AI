"""Helpers for :class:`OutputGate`."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NUMBER_RE = re.compile(r'(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)(?!\d)')


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
    text = str(value).strip()
    # strip currency/unit-ish suffixes
    text = text.replace(',', '')
    # keep digits, dot, minus
    cleaned = re.sub(r'[^0-9.\-]', '', text)
    if not cleaned or cleaned in {'.', '-', '-.'}:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _extract_numbers(text: str) -> list[Decimal]:
    if not text:
        return []
    # Ignore citation markers such as [1] when extracting numbers.
    text_for_numbers = re.sub(r'\[[^\]]*\]', ' ', text)
    nums: list[Decimal] = []
    for match in _NUMBER_RE.finditer(text_for_numbers):
        token = match.group(1).replace(',', '')
        try:
            nums.append(Decimal(token))
        except (InvalidOperation, ValueError):
            continue
    return nums


def _value_from_metric(metric: object) -> object:
    for attr in ('value', 'amount', 'figure', 'metric_value', 'result'):
        v = getattr(metric, attr, None) if not isinstance(metric, dict) else metric.get(attr)
        if v is not None:
            return v
    if isinstance(metric, dict):
        for k in ('value', 'amount', 'figure'):
            if k in metric:
                return metric[k]
    return metric


def _collect_citations(*args: object, **kwargs: object) -> list[object]:
    result: list[object] = []
    for key in ('citation', 'citations', 'sources', 'source'):
        val = kwargs.get(key)
        if val is None:
            continue
        if isinstance(val, (list, tuple, set)):
            result.extend(list(val))
        else:
            result.append(val)
    for arg in args:
        if isinstance(arg, (list, tuple, set)):
            # Could be citations if elements have document_id
            arg_seq = list(arg)
            if len(arg_seq) > 0 and hasattr(arg_seq[0], 'document_id'):
                result.extend(list(arg))
        elif arg is not None and hasattr(arg, 'document_id'):
            result.append(arg)
    # Remove None
    return [c for c in result if c is not None]


def _normalize_text(value: object) -> str:
    if value is None:
        return ''
    return str(value)
