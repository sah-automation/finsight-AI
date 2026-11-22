"""Unit tests for the dashboard layout repository SQL path.

The contract suite exercises the in-memory seam; these tests lock the wired
path's SQL shape, transaction ownership, tenant context and stale-save mapping
without a database.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.adapters.repositories.dashboard_layout_repository import DashboardLayoutRepository
from finsight.core.types import CompanyId, UserId
from finsight.domain.ports.dashboard_layout_repository import LayoutConflictError

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
USER = UserId('8e1a0000-0000-4000-8000-000000000001')


def _config() -> Any:
    default = SimpleNamespace(
        kpi_codes=['revenue'],
        charts=[SimpleNamespace(chart_id='revenue_trend', span='full')],
    )
    return SimpleNamespace(
        dashboard=SimpleNamespace(default_layout=default),
        kpi=SimpleNamespace(codes=('revenue', 'cash_flow')),
        charts=SimpleNamespace(specs={'revenue_trend': object(), 'margin_trend': object()}),
    )


def _row(version: int = 2, codes: str = '["revenue"]') -> dict[str, Any]:
    return {
        'contract_version': 1,
        'kpi_codes': codes,
        'charts': '[{"chart_id": "revenue_trend", "span": "full"}]',
        'version': version,
        'updated_at': None,
    }


class _Result:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[Any]:
        return self._rows


class _RecordingSession:
    def __init__(self, *, stale_save: bool = False) -> None:
        self.statements: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0
        self.stale_save = stale_save

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        sql = str(statement)
        self.statements.append((sql, dict(params or {})))
        if 'dashboard_layout_save' in sql and self.stale_save:
            return _Result()
        if 'dashboard_layout_get' in sql:
            return _Result([_row()])
        if 'dashboard_layout_save' in sql:
            return _Result([_row(version=3)])
        return _Result()

    def commit(self) -> None:
        self.commits += 1


def _sql(session: _RecordingSession) -> str:
    return '\n'.join(statement for statement, _ in session.statements)


def _params(session: _RecordingSession, fragment: str) -> dict[str, Any]:
    return next(params for statement, params in session.statements if fragment in statement)


def test_get_uses_visibility_and_clears_rls_without_committing() -> None:
    session = _RecordingSession()
    repository = DashboardLayoutRepository(config=_config(), session=session)

    record = asyncio.run(
        repository.get_layout(COMPANY, USER, visible_ids={'kpi_codes': ['revenue']})
    )

    assert record['kpi_codes'] == ['revenue']
    assert record['charts'] == [{'chart_id': 'revenue_trend', 'span': 'full'}]
    assert record['version'] == 2
    assert 'dashboard_layout_get' in _sql(session)
    assert 'set_config' in _sql(session) and 'NULL' in _sql(session)
    assert 'revenue' in str(_params(session, 'dashboard_layout_get')['visible_ids'])
    assert not any(
        keyword in statement
        for statement, _ in session.statements
        for keyword in ('INSERT', 'UPDATE', 'DELETE')
    )
    assert session.commits == 0


def test_save_uses_conditional_function_and_binds_json_payloads() -> None:
    session = _RecordingSession()
    repository = DashboardLayoutRepository(config=_config(), session=session)

    record = asyncio.run(
        repository.save_layout(
            COMPANY,
            USER,
            {'kpi_codes': ['revenue', 'cash_flow'], 'charts': []},
            2,
        )
    )

    assert record['version'] == 3
    params = _params(session, 'dashboard_layout_save')
    assert params['expected_version'] == 2
    assert params['company_id'] == str(COMPANY)
    assert params['user_id'] == str(USER)
    assert '"cash_flow"' in params['kpi_codes']
    assert 'NULL' in _sql(session)
    assert session.commits == 0


def test_stale_save_raises_conflict_carrying_current_layout() -> None:
    session = _RecordingSession(stale_save=True)
    repository = DashboardLayoutRepository(config=_config(), session=session)

    with pytest.raises(LayoutConflictError) as conflict:
        asyncio.run(repository.save_layout(COMPANY, USER, {'kpi_codes': []}, 0))

    assert conflict.value.current_layout['version'] == 2
    assert conflict.value.current_layout['kpi_codes'] == ['revenue']
    statements = [statement for statement, _ in session.statements]
    save_index = next(
        i for i, statement in enumerate(statements) if 'dashboard_layout_save' in statement
    )
    get_index = next(
        i for i, statement in enumerate(statements) if 'dashboard_layout_get' in statement
    )
    assert save_index < get_index
    assert 'NULL' in _sql(session)
    assert session.commits == 0


def test_delete_is_company_and_user_scoped_without_committing() -> None:
    session = _RecordingSession()
    repository = DashboardLayoutRepository(config=_config(), session=session)

    asyncio.run(repository.delete_layout(COMPANY, USER))

    params = _params(session, 'DELETE FROM dashboard_layouts')
    assert params == {'company_id': str(COMPANY), 'user_id': str(USER)}
    assert 'NULL' in _sql(session)
    assert session.commits == 0
