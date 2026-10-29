"""Ordered reranker result with fallback and threshold metadata."""

from __future__ import annotations

from typing import Any


class RerankResult(list[Any]):
    """List of candidates plus the trace and threshold used for this result."""

    def __init__(self, candidates: list[Any] | None = None, **metadata: Any) -> None:
        super().__init__(candidates or [])
        self.fallback = bool(metadata.get('fallback', False))
        self.disabled = bool(metadata.get('disabled', False))
        self.fallback_mode = metadata.get('fallback_mode')
        self.threshold = metadata.get('threshold')
        self.trace = dict(metadata.get('trace') or {})
        self.batch_count = int(metadata.get('batch_count', 0))
        self.model = metadata.get('model')
        self.provider = metadata.get('provider')

    @property
    def results(self) -> list[Any]:
        return list(self)

    @property
    def candidates(self) -> list[Any]:
        return list(self)

    @property
    def used_search_order(self) -> bool:
        return self.fallback

    @property
    def search_score_threshold(self) -> Any:
        return self.threshold


__all__ = ['RerankResult']
