"""Friendly result returned when the waiting line is full or times out."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BusyResult:
    """Typed busy result the ask flow can return instead of an error."""

    company_id: str
    reason: str = 'busy'
    message: str = 'Service is busy. Please try again in a moment.'
    retry_after_seconds: float = 1.0
    wait_seconds: float = 0.0
    queue_priority: str = 'quick_first'
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def busy(self) -> bool:
        return True

    @property
    def status(self) -> str:
        return 'busy'

    def __bool__(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            'company_id': self.company_id,
            'status': self.status,
            'reason': self.reason,
            'message': self.message,
            'retry_after_seconds': self.retry_after_seconds,
            'wait_seconds': self.wait_seconds,
            'queue_priority': self.queue_priority,
            'details': dict(self.details),
        }


__all__ = ['BusyResult']
