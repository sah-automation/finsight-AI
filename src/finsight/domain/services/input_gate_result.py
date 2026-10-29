"""Input gate result (pure domain)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InputGateResult:
    allowed: bool = True
    blocked: bool = False
    passed: bool = True
    normalized_question: str = ''
    normalized: str = ''
    question: str = ''
    original_question: str = ''
    reason: str | None = None
    blocked_reason: str | None = None
    message: str | None = None
    pii_detected: bool = False
    pii_kinds: list[str] = field(default_factory=list)
    pii_action: str | None = None
    injection_detected: bool = False
    max_length: int | None = None
    length: int = 0
    company_id: object = None

    def __post_init__(self) -> None:
        self.blocked = not self.allowed
        self.passed = self.allowed
        self.normalized_question = self.normalized_question or self.normalized
        self.normalized = self.normalized or self.normalized_question
        self.question = self.question or self.normalized
        self.blocked_reason = self.blocked_reason or self.reason
        self.reason = self.reason or self.blocked_reason
        self.message = self.message or self.reason
        self.length = len(self.normalized)

    def __bool__(self) -> bool:
        return bool(self.allowed)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bool):
            return bool(self.allowed) == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> object:
        return getattr(self, key, None)


__all__ = ['InputGateResult']
