"""Models and typed results for the ask-question flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AskResult:
    company_id: Any = None
    question: str = ''
    answer: Any = None
    citations: list[Any] = field(default_factory=list)
    model_id: Any = None
    status: str = 'ok'
    insufficient_data: bool = False
    busy: bool = False
    unavailable: bool = False


@dataclass
class UnavailableResult:
    company_id: Any = None
    question: str = ''
    reason: str = 'unavailable'
    message: str = 'AI service is temporarily unavailable. Please try again later.'
    model_id: str = 'unavailable'
    status: str = 'unavailable'

    @property
    def unavailable(self) -> bool:
        return True

    def __bool__(self) -> bool:
        return False


__all__ = ['AskResult', 'UnavailableResult']
