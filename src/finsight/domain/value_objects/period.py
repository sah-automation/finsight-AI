# Period - Value object for fiscal periods

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Period:
    """Immutable fiscal period with start and end dates."""

    start_date: date
    end_date: date
    label: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.start_date, date):
            raise TypeError('Period.start_date must be a date')
        if not isinstance(self.end_date, date):
            raise TypeError('Period.end_date must be a date')
        if self.end_date < self.start_date:
            raise ValueError('Period.end_date must be >= start_date')
        if self.label is not None and not isinstance(self.label, str):
            raise TypeError('Period.label must be a string or None')
