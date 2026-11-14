# Currency - Value object for currencies

from __future__ import annotations

from enum import StrEnum


class Currency(StrEnum):
    """ISO 4217 currency codes."""

    USD = 'USD'
    EUR = 'EUR'
    GBP = 'GBP'
    JPY = 'JPY'
    CAD = 'CAD'
    AUD = 'AUD'
