"""Unit tests for chart freshness fingerprints (issue #378)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from finsight.core.types import CompanyId
from finsight.domain.services.fingerprint import FingerprintService
from finsight.domain.services.kpi_computation_service import KpiComputationService

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
        self.calls: list[tuple[CompanyId, list[Any]]] = []

    async def get_fingerprint_data(
        self, company_id: CompanyId, chart_specs: Sequence[Any], **kwargs: Any
    ) -> dict[str, list[dict[str, Any]]]:
        self.calls.append((company_id, list(chart_specs)))
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


@pytest.mark.parametrize(
    ('field', 'new_value'),
    [
        ('kpi_code', 'gross_margin'),
        ('period', '2026-Q4'),
        ('chart_period', '2026-08'),
        ('document_version_id', 'version-2'),
        ('computation_rule_version', 'rule-v2'),
        ('computation_status', 'estimated'),
        ('source_citations', ['cit:v1:doc-1:p2']),
        ('conflict_marker', 'revenue|2026-Q3'),
        ('superseded_by_document_version_id', 'version-0'),
    ],
)
async def test_fingerprint_changes_when_an_included_field_changes(
    field: str, new_value: Any
) -> None:
    original = await FingerprintService(_StubRepository([_row()])).compute_fingerprint(
        COMPANY, SPEC
    )
    changed = await FingerprintService(
        _StubRepository([_row(**{field: new_value})])
    ).compute_fingerprint(COMPANY, SPEC)

    assert changed != original


async def test_fingerprint_excludes_timestamps_and_injected_display_labels() -> None:
    with_timestamps = _row(created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z')
    recomputed = _row(
        created_at='2026-11-23T12:00:00Z',
        updated_at='2026-11-23T12:00:00Z',
        display_label='Updating',
        estimation_method='quarterly_spread_equal',
    )

    first = await FingerprintService(_StubRepository([with_timestamps])).compute_fingerprint(
        COMPANY, SPEC
    )
    second = await FingerprintService(_StubRepository([recomputed])).compute_fingerprint(
        COMPANY, SPEC
    )

    assert first == second


async def test_fingerprint_is_independent_of_row_and_citation_order() -> None:
    revenue = _row(kpi_code='revenue', source_citations=['cit-a', 'cit-b'])
    margin = _row(kpi_code='gross_margin', source_citations=['cit-c'])

    first = await FingerprintService(_StubRepository([revenue, margin])).compute_fingerprint(
        COMPANY, SPEC
    )
    reordered = _row(kpi_code='revenue', source_citations=['cit-b', 'cit-a'])
    second = await FingerprintService(_StubRepository([margin, reordered])).compute_fingerprint(
        COMPANY, SPEC
    )

    assert first == second


async def test_empty_chart_has_a_deterministic_fingerprint() -> None:
    first = await FingerprintService(_StubRepository([])).compute_fingerprint(COMPANY, SPEC)
    second = await FingerprintService(_StubRepository([])).compute_fingerprint(COMPANY, SPEC)

    assert first == second
    assert len(first) == 64


async def test_compute_fingerprint_reads_only_the_requested_chart_for_the_company() -> None:
    repository = _StubRepository([_row()])

    await FingerprintService(repository).compute_fingerprint(COMPANY, SPEC)

    assert repository.calls == [(COMPANY, [SPEC])]


async def test_injected_display_label_does_not_change_the_fingerprint() -> None:
    # Display Label precedence (Updating > Estimated > Draft > null) is owned by
    # issue #375; this guards that injecting a label cannot feed back into the
    # fingerprint and keep a chart stale against its own label.
    labelled = KpiComputationService('rule-v1').apply_display_labels(
        [_row(computation_status='estimated')], updating=True
    )[0]

    assert labelled['display_label'] == 'Updating'

    plain = await FingerprintService(_StubRepository([_row()])).compute_fingerprint(COMPANY, SPEC)
    with_label = await FingerprintService(
        _StubRepository([_row(display_label=labelled['display_label'])])
    ).compute_fingerprint(COMPANY, SPEC)

    assert with_label == plain
