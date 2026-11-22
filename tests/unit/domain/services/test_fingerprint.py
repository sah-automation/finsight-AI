"""Unit tests for chart freshness fingerprints (issue #378)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.services.fingerprint import FingerprintService

from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

COMPANY: CompanyId = CompanyId('7e1a0000-0000-4000-8000-000000000001')
SPEC: dict[str, Any] = {'chart_id': 'revenue-trend', 'kpi_codes': ['revenue']}


def _row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'kpi_code': 'revenue',
        'period': '2026-Q3',
        'chart_period': '2026-07',
        'document_version_id': 'version-1',
        'computation_rule_version': 'rule-v1',
        'value': '100.00',
        'computation_status': 'computed',
        'source_citations': ['cit:v1:doc-1:p1'],
        'conflict_marker': None,
        'superseded_by_document_version_id': None,
    }
    return row | changes


class _StubRepository:
    """Minimal port stub returning the rows a fingerprint is derived from."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = [dict(row) for row in rows]

    async def get_fingerprint_data(
        self, company_id: CompanyId, chart_specs: Sequence[Any], **kwargs: Any
    ) -> dict[str, list[dict[str, Any]]]:
        return {str(chart_specs[0]['chart_id']): [dict(row) for row in self._rows]}


async def test_compute_fingerprint_is_a_stable_sha256_of_the_current_rows() -> None:
    service = FingerprintService(_StubRepository([_row()]))

    first = await service.compute_fingerprint(COMPANY, SPEC)
    again = await service.compute_fingerprint(COMPANY, SPEC)

    assert len(first) == 64
    assert int(first, 16) >= 0
    assert first == again


async def test_fingerprint_changes_when_the_exact_value_changes() -> None:
    original = await FingerprintService(_StubRepository([_row()])).compute_fingerprint(
        COMPANY, SPEC
    )
    changed = await FingerprintService(_StubRepository([_row(value='100.01')])).compute_fingerprint(
        COMPANY, SPEC
    )

    assert changed != original
