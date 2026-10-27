# MoneyUnits - Value object for monetary scales

from __future__ import annotations

from enum import StrEnum


class MoneyUnits(StrEnum):
    """Scale for monetary values."""

    UNITS = 'units'
    THOUSANDS = 'thousands'
    MILLIONS = 'millions'
    BILLIONS = 'billions'
