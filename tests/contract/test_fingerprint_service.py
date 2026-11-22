"""Contract tests for fingerprints over the KPI repository port (issue #378).

These exercise the real repository seam: rows are upserted as ``kpi_values``,
read back through ``kpi_current`` and projected by ``get_fingerprint_data``
before ``FingerprintService`` hashes them. They guard against drift between the
adapter's projection and the service's stable-field whitelist.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from finsight.adapters.repositories.kpi_repository import KpiRepository
from finsight.core.types import CompanyId
from finsight.domain.services.fingerprint import FingerprintService

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

pytestmark = pytest.mark.contract

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
OTHER_COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000002')
SPEC: dict[str, Any] = {'chart_id': 'revenue-trend', 'kpi_codes': ['revenue']}


def _row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'company_id': str(COMPANY),
        'kpi_code': 'revenue',
        'period': '2026-Q3',
        'chart_period': '2026-07',
        'period_start': '2026-07-01',
        'chart_period_start': '2026-07-01',
        'currency': 'USD',
        'units': 'USD',
        'value': '100.00',
        'computation_status': 'computed',
        'estimation_method': None,
        'document_version_id': 'version-1',
        'computation_rule_version': 'rule-v1',
        'source_citations': ['cit:v1:doc-1:p1'],
        'source_metric_ids': ['metric-1'],
        'superseded_by_document_version_id': None,
    }
    return row | changes


async def _fingerprint(
    rows: Sequence[Mapping[str, Any]],
    company: CompanyId = COMPANY,
    spec: Any = SPEC,
) -> str:
    repository = KpiRepository()
    await repository.upsert_batch(rows)
    return await FingerprintService(repository).compute_fingerprint(company, spec)


async def test_identical_recompute_and_reupsert_keep_the_fingerprint() -> None:
    repository = KpiRepository()
    await repository.upsert_batch([_row()])
    service = FingerprintService(repository)

    first = await service.compute_fingerprint(COMPANY, SPEC)
    await repository.upsert_batch([_row()])
    second = await service.compute_fingerprint(COMPANY, SPEC)

    assert first == second


@pytest.mark.parametrize(
    ('field', 'new_value'),
    [
        ('document_version_id', 'version-2'),
        ('computation_rule_version', 'rule-v2'),
        ('value', '100.01'),
        ('computation_status', 'estimated'),
        ('source_citations', ['cit:v1:doc-1:p2']),
        ('superseded_by_document_version_id', 'version-0'),
        ('kpi_code', 'gross_margin'),
        ('period', '2026-Q4'),
        ('chart_period', '2026-08'),
    ],
)
async def test_fingerprint_tracks_each_stable_field_through_the_port(
    field: str, new_value: Any
) -> None:
    baseline = await _fingerprint([_row()])
    changed = await _fingerprint([_row(**{field: new_value})])

    assert changed != baseline


async def test_conflict_keeps_both_cited_rows_and_tracks_either_value() -> None:
    first = _row(document_version_id='version-1', value='100.00')
    second = _row(
        document_version_id='version-2',
        value='120.00',
        source_citations=['cit:v1:doc-2:p1'],
    )
    single = await _fingerprint([first])

    repository = KpiRepository()
    await repository.upsert_batch([first, second])
    projected = await repository.get_fingerprint_data(COMPANY, [SPEC])
    conflicted = await FingerprintService(repository).compute_fingerprint(COMPANY, SPEC)

    assert len(projected[SPEC['chart_id']]) == 2
    assert all(row['conflict_marker'] for row in projected[SPEC['chart_id']])
    assert conflicted != single

    revised = _row(
        document_version_id='version-2',
        value='130.00',
        source_citations=['cit:v1:doc-2:p1'],
    )
    assert await _fingerprint([first, revised]) != conflicted


async def test_timestamps_are_excluded_through_the_port() -> None:
    early = await _fingerprint(
        [_row(created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z')]
    )
    late = await _fingerprint(
        [_row(created_at='2026-11-23T12:00:00Z', updated_at='2026-11-23T12:00:00Z')]
    )

    assert early == late


async def test_fingerprint_is_company_scoped_and_accepts_a_config_style_spec() -> None:
    repository = KpiRepository()
    await repository.upsert_batch([_row(), _row(company=str(OTHER_COMPANY), value='900.00')])
    service = FingerprintService(repository)
    spec = SimpleNamespace(chart_id=SPEC['chart_id'], kpi_codes=SPEC['kpi_codes'])

    mapped = await service.compute_fingerprint(COMPANY, SPEC)
    attributed = await service.compute_fingerprint(COMPANY, spec)

    assert mapped == attributed
    assert await service.compute_fingerprint(OTHER_COMPANY, spec) != mapped
