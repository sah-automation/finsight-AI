"""InsufficientData result type - a normal result, not a subtype of Answer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InsufficientData:
    """Explicit result returned when evidence is inadequate."""

    reason: str = 'insufficient data'
    company_id: object = None
    question: str | None = None
    citations: list[object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.citations is None:
            self.citations = []

    def __bool__(self) -> bool:
        return False


__all__ = ['InsufficientData']
