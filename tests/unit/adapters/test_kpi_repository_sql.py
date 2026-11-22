"""Unit tests for the KPI repository SQL path.

The contract suite exercises the in-memory seam; these tests lock the parts of
the wired path that cannot be observed without a database: bound filter values,
stable fingerprint ordering, and transaction ownership.
"""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.adapters.repositories import _kpi_repository_query as query
from finsight.adapters.repositories.kpi_repository import KpiRepository
from finsight.core.types import CompanyId

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')


def _row() -> dict[str, Any]:
    return {
        'company_id': str(COMPANY),
        'kpi_code': 'revenue',
        'period': '2025-Q1',
        'document_version_id': '10000000-0000-4000-8000-000000000001',
        'chart_period': '2025-Q1',
        'period_start': '2025-01-01',
        'chart_period_start': '2025-01-01',
        'currency': 'USD',
        'units': 'USD',
        'value': '100.00',
        'computation_status': 'computed',
        'source_citations': ['cite-1'],
        'computation_rule_version': 'rule-v1',
    }


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.commits = 0

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> None:
        del params
        self.statements.append(str(statement))

    def commit(self) -> None:
        self.commits += 1


def test_select_sql_binds_codes_individually_and_orders_stably() -> None:
    sql, params = query.build_select_sql(
        {
            'company_id': str(COMPANY),
            'kpi_codes': ['revenue', 'gross_margin'],
            'period_from': '2025-01-01',
        }
    )

    assert 'kpi_code IN (:kpi_code_0, :kpi_code_1)' in sql
    assert 'ORDER BY period_start DESC, kpi_code, chart_period, document_version_id' in sql
    assert params == {
        'company_id': str(COMPANY),
        'kpi_code_0': 'revenue',
        'kpi_code_1': 'gross_margin',
        'period_from': '2025-01-01',
    }


def test_upsert_batch_upserts_without_committing() -> None:
    session = _RecordingSession()
    repository = KpiRepository(session=session)

    written = asyncio.run(repository.upsert_batch([_row()], company_id=COMPANY))

    assert written == 1
    assert session.commits == 0
    assert any('ON CONFLICT' in statement for statement in session.statements)
    assert all('DELETE' not in statement for statement in session.statements)
