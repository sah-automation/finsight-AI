"""Deterministic calculator for structured metrics (pure domain)."""

from __future__ import annotations

from decimal import getcontext
from typing import Any

from ._calculator_calculate import _CalculatorCalculate
from ._calculator_operations import _CalculatorOperations
from .calculation_result import CalculationResult

getcontext().prec = 50


class Calculator(_CalculatorCalculate, _CalculatorOperations):
    """Pure calculation service supporting only safe operations."""

    _ALLOWED = {'sum', 'average', 'avg', 'mean', 'ratio', 'margin', 'variance', 'var'}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Configuration-like limits are accepted but unused.
        self.allowed_operations = {'sum', 'average', 'ratio', 'margin', 'variance'}

    # Convenience
    def sum(self, *args: Any, **kwargs: Any) -> CalculationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('operation', 'sum')
        return self.calculate(*args, **kwargs)  # type: ignore[no-any-return]

    def average(self, *args: Any, **kwargs: Any) -> CalculationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('operation', 'average')
        return self.calculate(*args, **kwargs)  # type: ignore[no-any-return]

    def avg(self, *args: Any, **kwargs: Any) -> CalculationResult:
        return self.average(*args, **kwargs)

    def mean(self, *args: Any, **kwargs: Any) -> CalculationResult:
        return self.average(*args, **kwargs)

    def ratio(self, *args: Any, **kwargs: Any) -> CalculationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('operation', 'ratio')
        return self.calculate(*args, **kwargs)  # type: ignore[no-any-return]

    def margin(self, *args: Any, **kwargs: Any) -> CalculationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('operation', 'margin')
        return self.calculate(*args, **kwargs)  # type: ignore[no-any-return]

    def variance(self, *args: Any, **kwargs: Any) -> CalculationResult:
        kwargs = dict(kwargs)
        kwargs.setdefault('operation', 'variance')
        return self.calculate(*args, **kwargs)  # type: ignore[no-any-return]

    def __call__(self, *args: Any, **kwargs: Any) -> CalculationResult:
        return self.calculate(*args, **kwargs)  # type: ignore[no-any-return]


def calculate(*args: Any, **kwargs: Any) -> CalculationResult:
    data = dict(kwargs)
    calc_kwargs = {}
    for key in ('company_id', 'period', 'category', 'document_id', 'version'):
        if key in data:
            calc_kwargs[key] = data.pop(key)
    merged: dict[str, object] = {}
    merged.update(data)
    for _k, _v in calc_kwargs.items():
        merged[_k] = _v
    return Calculator().calculate(*args, **merged)  # type: ignore[no-any-return]


# Aliases
CalculationService = Calculator
MetricCalculator = Calculator
CalculateService = Calculator
__all__ = [
    'CalculateService',
    'CalculationResult',
    'CalculationService',
    'Calculator',
    'MetricCalculator',
    'calculate',
]
