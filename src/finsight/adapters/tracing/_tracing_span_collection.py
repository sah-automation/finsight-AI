# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from finsight.domain.value_objects.span import Span


class _SpanCollection(list[Span]):
    """List-like span collection that is also callable for company filtering."""

    def __init__(self, spans: list[Span], company_id: Any = None, adapter: Any = None) -> None:
        self._all = list(spans)
        self._adapter = adapter
        if company_id is None:
            super().__init__(self._all)
        else:
            wanted = str(company_id)
            super().__init__(span for span in self._all if str(span.company_id) == wanted)

    def __call__(self, company_id: Any = None) -> _SpanCollection:
        return _SpanCollection(self._all, company_id, adapter=self._adapter)
