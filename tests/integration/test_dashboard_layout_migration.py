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


def _visible_ids(kpis: list[str] | None = None, charts: list[str] | None = None) -> str:
    """Role-permitted ids the caller also knows from config; unknown ids never enter this set."""
    default = _config_default()
    return json.dumps(
        {
            'kpi_codes': default['kpi_codes'] if kpis is None else kpis,
            'chart_ids': [chart['chart_id'] for chart in default['charts']]
            if charts is None
            else charts,
        }
    )


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


def _get(
    db: SimpleNamespace,
    visible: str | None = None,
) -> dict[str, Any] | None:
    row = db.conn.execute(
        text('SELECT * FROM dashboard_layout_get(:company_id, :user_id, CAST(:visible AS jsonb))'),
        {
            'company_id': db.company_id,
            'user_id': db.user_id,
            'visible': visible or _visible_ids(),
        },
    ).fetchone()
    return _layout_dict(row)


def _save(
    db: SimpleNamespace,
    version: int,
    kpis: list[str],
    charts: list[dict[str, str]],
    visible: str | None = None,
) -> dict[str, Any] | None:
    """One save attempt; no result means stale (the handler maps that to 409)."""
    row = db.conn.execute(
        text(
            'SELECT * FROM dashboard_layout_save('
            ':company_id, :user_id, :version, '
            'CAST(:kpis AS jsonb), CAST(:charts AS jsonb), CAST(:visible AS jsonb))'
        ),
        {
            'company_id': db.company_id,
            'user_id': db.user_id,
            'version': version,
            'kpis': json.dumps(kpis),
            'charts': json.dumps(charts),
            'visible': visible or _visible_ids(),
        },
    ).fetchone()
    return _layout_dict(row)


def _seed_layout(db: SimpleNamespace, kpis: list[str], charts: list[dict[str, str]]) -> None:
    """Store ids directly, simulating config drift or a legacy row."""
    db.conn.execute(
        text(
            'INSERT INTO dashboard_layouts '
            '(company_id, user_id, contract_version, kpi_codes, charts, version, updated_at) '
            'VALUES (:company_id, :user_id, 1, CAST(:kpis AS jsonb), '
            'CAST(:charts AS jsonb), 1, now())'
        ),
        {
            'company_id': db.company_id,
            'user_id': db.user_id,
            'kpis': json.dumps(kpis),
            'charts': json.dumps(charts),
        },
    )


def _stored(db: SimpleNamespace) -> list[object]:
    return db.conn.execute(
        text('SELECT * FROM dashboard_layouts WHERE company_id = :company_id'),
        {'company_id': db.company_id},
    ).fetchall()


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


def test_get_returns_config_default_without_writing_on_miss(layout_db: SimpleNamespace) -> None:
    layout = _get(layout_db)

    default = _config_default()
    assert layout is not None
    assert layout['contract_version'] == 1
    assert layout['kpi_codes'] == default['kpi_codes']
    assert layout['charts'] == default['charts']
    assert layout['version'] == 0
    assert layout['updated_at'] is None
    assert _stored(layout_db) == [], 'opening the dashboard never writes a row'


def test_first_save_creates_row_then_version_must_match(layout_db: SimpleNamespace) -> None:
    first_charts = [{'chart_id': 'revenue_trend', 'span': 'full'}]
    saved = _save(layout_db, 0, ['revenue'], first_charts)
    assert saved is not None
    assert saved['version'] == 1
    assert saved['kpi_codes'] == ['revenue']
    assert saved['charts'] == first_charts

    saved = _save(layout_db, 1, ['cash_flow'], [{'chart_id': 'margin_trend', 'span': 'half'}])
    assert saved is not None
    assert saved['version'] == 2
    assert saved['kpi_codes'] == ['cash_flow']


def test_stale_save_is_rejected_and_current_layout_is_readable(layout_db: SimpleNamespace) -> None:
    """A stale save yields no result; the handler maps that to 409 + the current layout."""
    _save(layout_db, 0, ['revenue'], [{'chart_id': 'revenue_trend', 'span': 'full'}])
    updated = _save(layout_db, 1, ['cash_flow'], [])
    assert updated is not None
    assert updated['version'] == 2

    for stale_version in (0, 1, 3):
        assert _save(layout_db, stale_version, ['burn_rate'], []) is None

    current = _get(layout_db)
    assert current is not None
    assert current['version'] == 2
    assert current['kpi_codes'] == ['cash_flow']
    assert current['charts'] == []


def test_read_drops_unpermitted_and_unknown_ids(layout_db: SimpleNamespace) -> None:
    stored_kpis = ['gross_margin', 'unknown_code', 'revenue']
    stored_charts = [
        {'chart_id': 'unknown_chart', 'span': 'full'},
        {'chart_id': 'revenue_trend', 'span': 'half'},
    ]
    _seed_layout(layout_db, stored_kpis, stored_charts)

    visible = _get(layout_db, _visible_ids(['revenue'], ['revenue_trend']))
    assert visible is not None
    assert visible['kpi_codes'] == ['revenue']
    assert visible['charts'] == [{'chart_id': 'revenue_trend', 'span': 'half'}]

    rows = _stored(layout_db)
    assert len(rows) == 1, 'filtering on read is non-destructive'
    assert list(rows[0].kpi_codes) == stored_kpis
    assert [chart['chart_id'] for chart in rows[0].charts] == ['unknown_chart', 'revenue_trend']


def test_save_drops_unknown_ids_and_role_unpermitted_ids(layout_db: SimpleNamespace) -> None:
    visibility = _visible_ids(['revenue', 'burn_rate'], ['revenue_trend'])
    saved = _save(
        layout_db,
        0,
        ['unknown_code', 'revenue', 'burn_rate'],
        [
            {'chart_id': 'unknown_chart', 'span': 'full'},
            {'chart_id': 'revenue_trend', 'span': 'full'},
        ],
        visibility,
    )
    assert saved is not None
    assert saved['kpi_codes'] == ['revenue', 'burn_rate']
    assert saved['charts'] == [{'chart_id': 'revenue_trend', 'span': 'full'}]

    rows = _stored(layout_db)
    assert len(rows) == 1
    assert list(rows[0].kpi_codes) == ['revenue', 'burn_rate']
    assert [chart['chart_id'] for chart in rows[0].charts] == ['revenue_trend']


def test_empty_after_filtering_falls_back_to_config_default(layout_db: SimpleNamespace) -> None:
    saved = _save(
        layout_db,
        0,
        ['unknown_code'],
        [{'chart_id': 'unknown_chart', 'span': 'full'}],
    )
    assert saved is not None
    default = _config_default()
    assert saved['kpi_codes'] == default['kpi_codes']
    assert saved['charts'] == default['charts']
