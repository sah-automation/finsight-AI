"""EvidenceResult (pure domain)."""

from __future__ import annotations


class EvidenceResult:
    """Outcome of an evidence check."""

    def __new__(cls, sufficient: bool = False, **kwargs: object) -> EvidenceResult:
        return object.__new__(cls)

    def __init__(self, sufficient: bool = False, **kwargs: object) -> None:
        self.sufficient = bool(sufficient)
        self.is_sufficient = self.sufficient
        self.has_evidence = bool(kwargs.get('has_evidence', sufficient))
        self.passed = self.sufficient
        self.allowed = self.sufficient
        self.ok = self.sufficient
        self.best_score = kwargs.get('best_score')
        self.score = self.best_score
        self.threshold = kwargs.get('threshold')
        self.min_score = self.threshold
        self.chunk_count = kwargs.get('chunk_count')
        self.min_chunks = kwargs.get('min_chunks')
        self.reranker_available = kwargs.get('reranker_available', True)
        self.reason = kwargs.get('reason')
        self.message = self.reason
        self.metadata = kwargs.get('metadata', {})
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def __bool__(self) -> bool:
        return bool(self.sufficient)

    __hash__ = object.__hash__

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bool):
            return bool(self.sufficient) == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> object:
        return getattr(self, key, None)
