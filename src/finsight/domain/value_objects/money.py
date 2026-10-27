# Money - Value object for financial amounts
# Money always uses Decimal for precision; no floats for amounts.

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .currency import Currency
from .money_units import MoneyUnits


@dataclass(frozen=True)
class Money:
    """Immutable monetary value with currency and units."""

    amount: Decimal
    currency: Currency = Currency.USD
    units: MoneyUnits = MoneyUnits.UNITS

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError('Money.amount must be a Decimal')
        if not isinstance(self.currency, Currency):
            raise TypeError('Money.currency must be a Currency')
        if not isinstance(self.units, MoneyUnits):
            raise TypeError('Money.units must be a MoneyUnits')

    def __str__(self) -> str:
        return f'{self.amount} {self.currency.value} ({self.units.value})'
