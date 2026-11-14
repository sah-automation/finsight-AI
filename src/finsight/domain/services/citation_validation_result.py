"""CitationValidationResult (pure domain)."""

from __future__ import annotations


class CitationValidationResult:
    def __new__(cls, valid: bool = False, **kwargs: object) -> CitationValidationResult:
        return object.__new__(cls)

    def __init__(self, valid: bool = False, **kwargs: object) -> None:
        self.valid = bool(valid)
        self.passed = self.valid
        self.allowed = self.valid
        self.ok = self.valid
        self.has_citation = bool(kwargs.get('has_citation', self.valid))
        self.has_citations = self.has_citation
        self.presence = self.has_citation
        self.citations = kwargs.get('citations', [])
        self.invalid = kwargs.get('invalid', [])
        self.errors = kwargs.get('errors', [])
        self.reason = kwargs.get('reason')
        self.message = self.reason
        self.metadata = kwargs.get('metadata', {})
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def __bool__(self) -> bool:
        return bool(self.valid)

    __hash__ = object.__hash__

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bool):
            return bool(self.valid) == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> object:
        return getattr(self, key, None)
