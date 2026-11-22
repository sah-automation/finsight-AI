"""Migration tests for the Phase 2 saved-layout store (issue #369).

Verify the ``dashboard_layouts`` table (§3.4 of phase2_spec.md) and the
database primitives the layout repository uses: optimistic locking, the
config default on a miss with no row written, and id filtering on read/save.

Like ``test_kpi_migration.py`` this is integration-only and profile-driven:
the same Alembic chain is exercised against whichever PostgreSQL the active
``ENVIRONMENT`` profile points at (local/CI standard path or Neon pilot).
Nothing in this file hard-codes a host, port or database name.
"""

from __future__ import annotations

import json
import socket
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote_plus

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from finsight.core.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / 'migrations'
ALEMBIC_INI = REPO_ROOT / 'alembic.ini'

_TIMESTAMP = 'timestamp with time zone'


def _postgres_reachable() -> bool:
    try:
        settings = load_config().vector_store
        with socket.create_connection((str(settings.host), int(settings.port)), timeout=2):
            return True
    except Exception:  # pragma: no cover - exercised only without Postgres  # noqa: BLE001
        return False


def _database_url() -> str:
    settings = load_config().vector_store
    username = quote_plus(settings.username)
    password = quote_plus(settings.password)
    return (
        f'postgresql+psycopg://{username}:{password}'
        f'@{settings.host}:{settings.port}/{settings.database}'
        f'?sslmode={settings.ssl_mode}'
    )


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(300),
    pytest.mark.skipif(
        not _postgres_reachable(),
        reason='PostgreSQL is not available (integration-only test)',
    ),
]


@pytest.fixture()
def layout_db() -> SimpleNamespace:
    """Bring the schema to head and expose an isolated company-scoped connection."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option('script_location', str(MIGRATIONS_DIR))
    command.upgrade(alembic_cfg, 'head')

    engine = create_engine(_database_url(), pool_pre_ping=True)
    connection = engine.connect()
    company_id = str(uuid.uuid4())
    connection.execute(
        text("SELECT set_config('app.company_id', :company_id, false)"),
        {'company_id': company_id},
    )
    try:
        yield SimpleNamespace(conn=connection, company_id=company_id, user_id=str(uuid.uuid4()))
    finally:
        connection.rollback()
        connection.close()
        engine.dispose()


def _config_default() -> dict[str, Any]:
    """The config-defined default layout, from the config module's typed models."""
    default = load_config().dashboard.default_layout
    return {
        'kpi_codes': list(default.kpi_codes),
        'charts': [{'chart_id': chart.chart_id, 'span': chart.span} for chart in default.charts],
    }


def _json(values: object) -> str:
    return json.dumps(values)


def _layout_dict(row: object | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        'contract_version': row.contract_version,
        'kpi_codes': list(row.kpi_codes),
        'charts': [dict(chart) for chart in row.charts],
        'version': row.version,
        'updated_at': row.updated_at,
    }


def _get_layout(
    conn: object,
    company_id: str,
    user_id: str,
    allowed_kpis: str,
    allowed_charts: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            'SELECT * FROM dashboard_layout_get('
            ':company_id, :user_id, CAST(:allowed_kpis AS jsonb), CAST(:allowed_charts AS jsonb))'
        ),
        {
            'company_id': company_id,
            'user_id': user_id,
            'allowed_kpis': allowed_kpis,
            'allowed_charts': allowed_charts,
        },
    ).fetchone()
    return _layout_dict(row)


def _save_layout(
    conn: object,
    company_id: str,
    user_id: str,
    version: int,
    kpi_codes: str,
    charts: str,
    allowed_kpis: str,
    allowed_charts: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            'SELECT * FROM dashboard_layout_save('
            ':company_id, :user_id, :version, '
            'CAST(:kpi_codes AS jsonb), CAST(:charts AS jsonb), '
            'CAST(:allowed_kpis AS jsonb), CAST(:allowed_charts AS jsonb))'
        ),
        {
            'company_id': company_id,
            'user_id': user_id,
            'version': version,
            'kpi_codes': kpi_codes,
            'charts': charts,
            'allowed_kpis': allowed_kpis,
            'allowed_charts': allowed_charts,
        },
    ).fetchone()
    return _layout_dict(row)


def _allowed() -> tuple[str, str]:
    default = _config_default()
    return (
        _json(default['kpi_codes']),
        _json([chart['chart_id'] for chart in default['charts']]),
    )


def _stored(conn: object, company_id: str) -> list[object]:
    return conn.execute(
        text('SELECT * FROM dashboard_layouts WHERE company_id = :company_id'),
        {'company_id': company_id},
    ).fetchall()


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------


def test_dashboard_layouts_schema_matches_spec(layout_db: SimpleNamespace) -> None:
    conn = layout_db.conn
    columns = {
        row.column_name: (row.data_type, row.is_nullable)
        for row in conn.execute(
            text(
                'SELECT column_name, data_type, is_nullable '
                "FROM information_schema.columns WHERE table_name = 'dashboard_layouts' "
                'ORDER BY ordinal_position'
            )
        )
    }
    assert columns == {
        'company_id': ('uuid', 'NO'),
        'user_id': ('uuid', 'NO'),
        'contract_version': ('integer', 'NO'),
        'kpi_codes': ('jsonb', 'NO'),
        'charts': ('jsonb', 'NO'),
        'version': ('integer', 'NO'),
        'updated_at': (_TIMESTAMP, 'NO'),
    }

    primary_key = conn.execute(
        text(
            'SELECT pg_get_constraintdef(oid) FROM pg_constraint '
            "WHERE conrelid = 'dashboard_layouts'::regclass AND contype = 'p'"
        )
    ).scalar()
    assert primary_key == 'PRIMARY KEY (company_id, user_id)'

    rls_enabled, rls_forced = conn.execute(
        text(
            'SELECT relrowsecurity, relforcerowsecurity FROM pg_class '
            "WHERE oid = 'dashboard_layouts'::regclass"
        )
    ).one()
    assert rls_enabled is True
    assert rls_forced is True


def test_no_layout_store_configuration_key() -> None:
    """ADR-0011 dropped layout_store: there is no second store path or switch."""
    assert 'layout_store' not in load_config().dashboard.model_dump()


# ---------------------------------------------------------------------------
# read: config default on miss
# ---------------------------------------------------------------------------


def test_get_returns_config_default_without_writing_on_miss(layout_db: SimpleNamespace) -> None:
    conn = layout_db.conn
    allowed_kpis, allowed_charts = _allowed()

    layout = _get_layout(
        conn, layout_db.company_id, layout_db.user_id, allowed_kpis, allowed_charts
    )

    default = _config_default()
    assert layout is not None
    assert layout['contract_version'] == 1
    assert layout['kpi_codes'] == default['kpi_codes']
    assert layout['charts'] == default['charts']
    assert layout['version'] == 0
    assert layout['updated_at'] is None
    assert _stored(conn, layout_db.company_id) == [], 'opening the dashboard never writes a row'


# ---------------------------------------------------------------------------
# save: optimistic locking
# ---------------------------------------------------------------------------


def test_first_save_creates_row_then_version_must_match(layout_db: SimpleNamespace) -> None:
    conn = layout_db.conn
    allowed_kpis, allowed_charts = _allowed()
    first = {'kpi_codes': ['revenue'], 'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}]}

    saved = _save_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        0,
        _json(first['kpi_codes']),
        _json(first['charts']),
        allowed_kpis,
        allowed_charts,
    )
    assert saved is not None
    assert saved['version'] == 1
    assert saved['kpi_codes'] == first['kpi_codes']
    assert saved['charts'] == first['charts']

    second = {'kpi_codes': ['cash_flow'], 'charts': [{'chart_id': 'margin_trend', 'span': 'half'}]}
    saved = _save_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        1,
        _json(second['kpi_codes']),
        _json(second['charts']),
        allowed_kpis,
        allowed_charts,
    )
    assert saved is not None
    assert saved['version'] == 2
    assert saved['kpi_codes'] == second['kpi_codes']


def test_stale_save_is_rejected_and_current_layout_is_readable(layout_db: SimpleNamespace) -> None:
    """A stale version yields no save result; the handler maps that to 409 + current layout."""
    conn = layout_db.conn
    allowed_kpis, allowed_charts = _allowed()
    original = {'kpi_codes': ['revenue'], 'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}]}
    _save_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        0,
        _json(original['kpi_codes']),
        _json(original['charts']),
        allowed_kpis,
        allowed_charts,
    )

    for stale_version in (0, 1):
        rejected = _save_layout(
            conn,
            layout_db.company_id,
            layout_db.user_id,
            stale_version,
            _json(['burn_rate']),
            _json([]),
            allowed_kpis,
            allowed_charts,
        )
        assert rejected is None, f'version {stale_version} must not overwrite version 1'

    current = _get_layout(
        conn, layout_db.company_id, layout_db.user_id, allowed_kpis, allowed_charts
    )
    assert current is not None
    assert current['version'] == 1
    assert current['kpi_codes'] == original['kpi_codes']
    assert current['charts'] == original['charts']


# ---------------------------------------------------------------------------
# role filtering on read and save
# ---------------------------------------------------------------------------


def test_read_drops_unpermitted_and_unknown_ids(layout_db: SimpleNamespace) -> None:
    conn = layout_db.conn
    stored_payload = {
        'kpi_codes': ['gross_margin', 'unknown_code', 'revenue'],
        'charts': [
            {'chart_id': 'unknown_chart', 'span': 'full'},
            {'chart_id': 'revenue_trend', 'span': 'half'},
        ],
    }
    _save_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        0,
        _json(stored_payload['kpi_codes']),
        _json(stored_payload['charts']),
        _json(['revenue', 'gross_margin', 'burn_rate', 'unknown_code']),
        _json(['revenue_trend', 'margin_trend', 'unknown_chart']),
    )

    visible = _get_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        _json(['revenue']),
        _json(['revenue_trend']),
    )
    assert visible is not None
    assert visible['kpi_codes'] == ['revenue']
    assert visible['charts'] == [{'chart_id': 'revenue_trend', 'span': 'half'}]

    rows = _stored(conn, layout_db.company_id)
    assert len(rows) == 1, 'filtering on read is non-destructive'
    assert list(rows[0].kpi_codes) == stored_payload['kpi_codes']


def test_save_drops_unpermitted_and_unknown_ids_before_persisting(
    layout_db: SimpleNamespace,
) -> None:
    conn = layout_db.conn
    saved = _save_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        0,
        _json(['unknown_code', 'revenue', 'burn_rate']),
        _json(
            [
                {'chart_id': 'unknown_chart', 'span': 'full'},
                {'chart_id': 'revenue_trend', 'span': 'full'},
            ]
        ),
        _json(['revenue', 'burn_rate']),
        _json(['revenue_trend']),
    )
    assert saved is not None
    assert saved['kpi_codes'] == ['revenue', 'burn_rate']
    assert saved['charts'] == [{'chart_id': 'revenue_trend', 'span': 'full'}]

    rows = _stored(conn, layout_db.company_id)
    assert len(rows) == 1
    assert list(rows[0].kpi_codes) == ['revenue', 'burn_rate']
    assert [chart['chart_id'] for chart in rows[0].charts] == ['revenue_trend']


def test_empty_after_filtering_falls_back_to_config_default(layout_db: SimpleNamespace) -> None:
    conn = layout_db.conn
    allowed_kpis, allowed_charts = _allowed()
    default = _config_default()

    saved = _save_layout(
        conn,
        layout_db.company_id,
        layout_db.user_id,
        0,
        _json(['unknown_code']),
        _json([{'chart_id': 'unknown_chart', 'span': 'full'}]),
        allowed_kpis,
        allowed_charts,
    )
    assert saved is not None
    assert saved['kpi_codes'] == default['kpi_codes']
    assert saved['charts'] == default['charts']
