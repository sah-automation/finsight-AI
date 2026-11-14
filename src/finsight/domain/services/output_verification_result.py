"""OutputVerificationResult (pure domain)."""

from __future__ import annotations


class OutputVerificationResult:
    def __new__(cls, passed: bool = False, **kwargs: object) -> OutputVerificationResult:
        return object.__new__(cls)

    def __init__(self, passed: bool = False, **kwargs: object) -> None:
        self.passed = bool(passed)
        self.valid = self.passed
        self.allowed = self.passed
        self.ok = self.passed
        self.citation_ok = bool(kwargs.get('citation_ok', passed))
        self.citations_ok = self.citation_ok
        self.numbers_ok = bool(kwargs.get('numbers_ok', passed))
        self.number_ok = self.numbers_ok
        self.pii_ok = bool(kwargs.get('pii_ok', passed))
        self.citation_present = bool(kwargs.get('citation_present', self.citation_ok))
        self.numbers = kwargs.get('numbers', [])
        self.allowed_numbers = kwargs.get('allowed_numbers', [])
        self.mismatched_numbers = kwargs.get('mismatched_numbers', [])
        self.pii_kinds = kwargs.get('pii_kinds', [])
        self.mode = kwargs.get('mode', 'full_answer')
        self.timing = self.mode
        self.reasons = kwargs.get('reasons', [])
        self.reason = kwargs.get('reason')
        self.message = self.reason
        self.metadata = kwargs.get('metadata', {})
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def __bool__(self) -> bool:
        return bool(self.passed)

    __hash__ = object.__hash__

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bool):
            return bool(self.passed) == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> object:
        return getattr(self, key, None)
