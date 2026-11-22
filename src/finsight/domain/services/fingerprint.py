"""Canonical freshness fingerprints for chart KPI rows (issue #378).

A fingerprint is derived on read, never stored. Only the stable fields named in
the Phase 2 spec are hashed: timestamps and injected display labels are excluded
so an ``Updating`` badge cannot keep a chart stale against its own fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import CompanyId
    from finsight.domain.ports.kpi_repository import KpiRepository

_FINGERPRINT_FIELDS = (
    'kpi_code',
    'period',
    'chart_period',
    'document_version_id',
    'computation_rule_version',
    'value',
    'computation_status',
    'source_citations',
    'conflict_marker',
    'superseded_by_document_version_id',
)


def _spec_field(spec: Any, field: str) -> Any:
    if isinstance(spec, Mapping):
        return spec.get(field)
    return getattr(spec, field, None)


def _exact(value: Any) -> Any:
    """Normalise a field to an exact JSON scalar without reading a clock."""
    return None if value is None else str(value)


def _canonical_row(row: Mapping[str, Any]) -> dict[str, Any]:
    citations = row.get('source_citations') or []
    if isinstance(citations, (str, bytes)):
        citations = [citations]
    canonical: dict[str, Any] = {
        field: _exact(row.get(field))
        for field in _FINGERPRINT_FIELDS
        if field != 'source_citations'
    }
    canonical['source_citations'] = sorted(
        _exact(citation) for citation in citations if citation is not None
    )
    return canonical


def _canonical_json(rows: Sequence[Mapping[str, Any]]) -> str:
    encoded_rows = sorted(
        json.dumps(_canonical_row(row), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        for row in rows
    )
    return json.dumps(encoded_rows, separators=(',', ':'), ensure_ascii=False)


class FingerprintService:
    """Derive a canonical freshness fingerprint from a chart's current KPI rows."""

    def __init__(self, repository: KpiRepository) -> None:
        self._repository = repository

    async def compute_fingerprint(self, company_id: CompanyId, chart_spec: Any) -> str:
        """Return the SHA-256 hex fingerprint of the chart's current KPI rows."""
        data = await self._repository.get_fingerprint_data(company_id, [chart_spec])
        chart_id = str(_spec_field(chart_spec, 'chart_id'))
        return hashlib.sha256(_canonical_json(data.get(chart_id, ())).encode('utf-8')).hexdigest()


__all__ = ['FingerprintService']
