"""CalculationResult (pure domain)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal


class CalculationResult:
    """Outcome of a calculation."""

    def __init__(
        self,
        operation: str,
        value: Decimal | None,
        values: list[Decimal],
        source_metric_ids: list[str],
        source_chunk_ids: list[str],
        metadata: dict[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self.operation = str(operation).lower()
        self.name = self.operation
        self.op = self.operation
        self.value = value
        self.result = value
        self.total = value
        self.output = value
        self.computed = value
        self.answer = value
        self.values = list(values)
        self.inputs = list(values)
        self.numbers = list(values)
        self.count = len(values)
        self.n = len(values)
        self.source_metric_ids = list(source_metric_ids)
        self.metric_ids = list(source_metric_ids)
        self.source_metrics = list(source_metric_ids)
        self.source_chunk_ids = list(source_chunk_ids)
        self.chunk_ids = list(source_chunk_ids)
        self.cited_chunk_numbers = list(source_chunk_ids)
        self.source_chunks = list(source_chunk_ids)
        self.metadata = metadata or {}
        self.filters = self.metadata.get('filters', {})
        self.details = self.metadata
        self.kwargs = kwargs
        for key, val in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, val)

    def __repr__(self) -> str:
        return f'CalculationResult(operation={self.operation!r}, value={self.value!r})'

    def __bool__(self) -> bool:
        return self.value is not None

    def __getitem__(self, key: str) -> object:
        mapping = {
            'operation': self.operation,
            'value': self.value,
            'result': self.result,
            'values': self.values,
            'count': self.count,
            'source_metric_ids': self.source_metric_ids,
            'source_chunk_ids': self.source_chunk_ids,
            'metadata': self.metadata,
        }
        if key in mapping:
            return mapping[key]
        return getattr(self, key, None)

