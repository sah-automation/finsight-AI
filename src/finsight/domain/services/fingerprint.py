"""Canonical freshness fingerprints for chart KPI rows (issue #378).

A fingerprint is derived on read, never stored. Only the stable fields named in
the Phase 2 spec are hashed: timestamps and the injected ``Updating`` Display
Label are excluded, so applying a label cannot keep a chart stale against its
own fingerprint.

Issue #378 mandates this path for ``FingerprintService``; the generic
file/class naming rule is therefore recorded as an explicit, ticket-backed
exception in ``tests/architecture/test_invariants.py``, as done for #377.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.kpi_repository import FINGERPRINT_FIELDS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import CompanyId
    from finsight.domain.ports.kpi_repository import KpiRepository


def _spec_value(spec: Any, field: str) -> Any:
    if isinstance(spec, Mapping):
        return spec.get(field)
    return getattr(spec, field, None)


def _json_scalar(value: Any) -> Any:
    """Keep the exact scalar; only ``None`` becomes an explicit JSON null."""
    return None if value is None else value


def _canonical_row(row: Mapping[str, Any]) -> dict[str, Any]:
    citations = row.get('source_citations') or []
    if isinstance(citations, (str, bytes)):
        citations = [citations]
    canonical: dict[str, Any] = {
        field: _json_scalar(row.get(field))
        for field in FINGERPRINT_FIELDS
        if field != 'source_citations'
    }
    canonical['source_citations'] = sorted(
        str(citation) for citation in citations if citation is not None
    )
    return canonical


def _canonical_json(rows: Sequence[Mapping[str, Any]]) -> str:
    encoded_rows = sorted(
        json.dumps(
            _canonical_row(row),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            default=str,
        )
        for row in rows
    )
    return json.dumps(encoded_rows, separators=(',', ':'), ensure_ascii=False, default=str)


class FingerprintService:
    """Derive a canonical freshness fingerprint from a chart's current KPI rows."""

    def __init__(self, repository: KpiRepository) -> None:
        self._repository = repository

    async def compute_fingerprint(self, company_id: CompanyId, chart_spec: Any) -> str:
        """Return the SHA-256 hex fingerprint of the chart's current KPI rows."""
        rows_by_chart_id = await self._repository.get_fingerprint_data(company_id, [chart_spec])
        chart_id = str(_spec_value(chart_spec, 'chart_id'))
        rows = rows_by_chart_id.get(chart_id, ())
        return hashlib.sha256(_canonical_json(rows).encode('utf-8')).hexdigest()


__all__ = ['FingerprintService']
