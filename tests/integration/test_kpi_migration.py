"""Migration tests for the Phase 2 KPI store (issue #368).

Verify the ``kpi_values`` table (columns, primary key, indexes, checks, RLS),
the ``kpi_rebuild_state`` table and the ``kpi_current`` read view's selection,
conflict, supersession and retention logic.

The test is profile-driven: it runs against whichever PostgreSQL the active
``ENVIRONMENT`` profile points at.  The same Alembic chain and the same
assertions therefore hold on the local/CI Postgres instance (standard path)
and on Neon (pilot) when the suite is pointed at a pilot profile.  Nothing in
this file hard-codes a host, port or database name.

Like ``test_migration_roundtrip.py`` this is integration-only: it skips
cleanly when the test-profile PostgreSQL is unreachable.  The local test
user is a superuser, so row-level security is asserted through the catalog
flags (enabled + forced) rather than through behavioural fail-closed checks.
"""

from __future__ import annotations

import socket
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

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


def _retention_defaults() -> tuple[int, int]:
    """The configured ``version_retention_days`` / ``deleted_retention_days``."""
    documents = load_config().documents
    if documents is None:  # pragma: no cover - schema.yaml always ships the section
        return 365, 30
    return int(documents.version_retention_days), int(documents.deleted_retention_days)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(300),
    pytest.mark.skipif(
        not _postgres_reachable(),
        reason='PostgreSQL is not available (integration-only test)',
    ),
]


@pytest.fixture()
def kpi_db() -> SimpleNamespace:
    """Bring the schema to head and expose one company-scoped connection.

    Every seed row is written inside the connection's open transaction and
    rolled back on teardown, so the fixture leaves no residue behind.
    """
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
    _ensure_company_partitions(connection, company_id)
    try:
        yield SimpleNamespace(conn=connection, company_id=company_id)
    finally:
        # Rolls back the seeds and the per-company partitions together.
        connection.rollback()
        connection.close()
        engine.dispose()


def _ensure_company_partitions(conn: object, company_id: str) -> None:
    """Create the LIST partitions the seed rows insert into.

    ``documents`` and ``document_versions`` are partitioned by ``company_id``
    (Phase 1), so a fresh company needs its partitions before any seed row can
    land.  Names follow ``PartitionManager``'s convention and the DDL is rolled
    back with the rest of the fixture's transaction.
    """
    clean_id = company_id.replace('-', '')
    for table_name in ('documents', 'document_versions'):
        # The bound value is inlined exactly as PartitionManager does it:
        # partition-bound DDL cannot infer parameter types server-side, and
        # ``company_id`` is a locally generated uuid.
        conn.execute(
            text(
                f'CREATE TABLE IF NOT EXISTS {table_name}_company_{clean_id} '
                f"PARTITION OF {table_name} FOR VALUES IN ('{company_id}')"
            )
        )


# ---------------------------------------------------------------------------
# seed helpers
# ---------------------------------------------------------------------------


def _seed_company(conn: object, company_id: str) -> None:
    conn.execute(
        text('INSERT INTO companies (id, name, slug) VALUES (:id, :name, :slug)'),
        {'id': company_id, 'name': 'KPI migration test', 'slug': f'kpi-test-{company_id[:8]}'},
    )


def _seed_document(
    conn: object,
    company_id: str,
    *,
    status: str = 'final',
    deleted_at: datetime | None = None,
) -> str:
    document_id = str(uuid.uuid4())
    conn.execute(
        text(
            'INSERT INTO documents (id, company_id, filename, storage_key, status, deleted_at) '
            'VALUES (CAST(:id AS uuid), CAST(:company_id AS uuid), :filename, :storage_key, '
            ':status, CAST(:deleted_at AS timestamptz))'
        ),
        {
            'id': document_id,
            'company_id': company_id,
            'filename': 'report.pdf',
            'storage_key': f'fixtures/{document_id}.pdf',
            'status': status,
            'deleted_at': deleted_at,
        },
    )
    return document_id


def _seed_version(
    conn: object,
    company_id: str,
    document_id: str,
    *,
    version: int = 1,
    created_at: datetime | None = None,
) -> str:
    version_id = str(uuid.uuid4())
    conn.execute(
        text(
            'INSERT INTO document_versions (id, company_id, document_id, version, state, created_at) '
            'VALUES (CAST(:id AS uuid), CAST(:company_id AS uuid), CAST(:document_id AS uuid), '
            ':version, :state, COALESCE(CAST(:created_at AS timestamptz), now()))'
        ),
        {
            'id': version_id,
            'company_id': company_id,
            'document_id': document_id,
            'version': version,
            'state': 'committed',
            'created_at': created_at,
        },
    )
    return version_id


def _seed_kpi(
    conn: object,
    company_id: str,
    version_id: str,
    *,
    kpi_code: str = 'revenue',
    period: str = '2026-09',
    chart_period: str | None = None,
    period_start: str = '2026-09-01',
    chart_period_start: str | None = None,
    currency: str = 'USD',
    units: str = 'usd',
    value: str | None = '100.00',
    computation_status: str = 'computed',
    estimation_method: str | None = None,
    superseded_by: str | None = None,
    computation_rule_version: str = 'rules-v1',
) -> None:
    conn.execute(
        text(
            'INSERT INTO kpi_values ('
            'company_id, kpi_code, period, document_version_id, chart_period, '
            'period_start, chart_period_start, currency, units, value, '
            'computation_status, estimation_method, source_citations, '
            'computation_rule_version, superseded_by_document_version_id, '
            'created_at, updated_at'
            ') VALUES ('
            'CAST(:company_id AS uuid), :kpi_code, :period, '
            'CAST(:document_version_id AS uuid), :chart_period, '
            'CAST(:period_start AS date), CAST(:chart_period_start AS date), '
            ':currency, :units, CAST(:value AS numeric), '
            ':computation_status, :estimation_method, '
            'CAST(:source_citations AS jsonb), '
            ':computation_rule_version, '
            'CAST(:superseded_by AS uuid), now(), now())'
        ),
        {
            'company_id': company_id,
            'kpi_code': kpi_code,
            'period': period,
            'document_version_id': version_id,
            'chart_period': chart_period or period,
            'period_start': period_start,
            'chart_period_start': chart_period_start or period_start,
            'currency': currency,
            'units': units,
            'value': value,
            'computation_status': computation_status,
            'estimation_method': estimation_method,
            'source_citations': '["citation-1"]',
            'computation_rule_version': computation_rule_version,
            'superseded_by': superseded_by,
        },
    )


def _view_rows(conn: object, company_id: str) -> list[object]:
    return conn.execute(
        text(
            'SELECT document_version_id, value, is_selected, conflict_marker '
            'FROM kpi_current WHERE company_id = :company_id'
        ),
        {'company_id': company_id},
    ).fetchall()


def _constraint_definition(conn: object, table: str, kind: str) -> str:
    return conn.execute(
        text(
            'SELECT pg_get_constraintdef(oid) FROM pg_constraint '
            'WHERE conrelid = CAST(:table AS regclass) AND contype = :kind'
        ),
        {'table': table, 'kind': kind},
    ).scalar()


# ---------------------------------------------------------------------------
# schema: kpi_values
# ---------------------------------------------------------------------------


def test_kpi_values_schema_matches_spec(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    relkind = conn.execute(
        text(
            'SELECT c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace '
            "WHERE n.nspname = 'public' AND c.relname = 'kpi_values'"
        )
    ).scalar()
    # Phase 2 stores one KPI table with no monthly partitioning.
    assert relkind == 'r', 'kpi_values must be a plain (non-partitioned) table'

    columns = {
        row.column_name: (row.data_type, row.is_nullable)
        for row in conn.execute(
            text(
                'SELECT column_name, data_type, is_nullable '
                "FROM information_schema.columns WHERE table_name = 'kpi_values' "
                'ORDER BY ordinal_position'
            )
        )
    }
    expected = {
        'company_id': ('uuid', 'NO'),
        'kpi_code': ('text', 'NO'),
        'period': ('text', 'NO'),
        'document_version_id': ('uuid', 'NO'),
        'chart_period': ('text', 'NO'),
        'period_start': ('date', 'NO'),
        'chart_period_start': ('date', 'NO'),
        'currency': ('text', 'NO'),
        'units': ('text', 'NO'),
        'value': ('numeric', 'YES'),
        'computation_status': ('text', 'NO'),
        'estimation_method': ('text', 'YES'),
        'source_citations': ('jsonb', 'NO'),
        'computation_rule_version': ('text', 'NO'),
        'superseded_by_document_version_id': ('uuid', 'YES'),
        'created_at': (_TIMESTAMP, 'NO'),
        'updated_at': (_TIMESTAMP, 'NO'),
    }
    assert columns == expected

    assert _constraint_definition(conn, 'kpi_values', 'p') == (
        'PRIMARY KEY (company_id, kpi_code, period, document_version_id, chart_period)'
    )

    indexes = {
        row.indexname: row.indexdef
        for row in conn.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'kpi_values'")
        )
    }
    assert 'kpi_values_company_code_start' in indexes
    assert 'kpi_values_company_chart_start' in indexes
    assert '(company_id, kpi_code, period_start DESC)' in indexes['kpi_values_company_code_start']
    assert '(company_id, chart_period_start)' in indexes['kpi_values_company_chart_start']

    rls_enabled = conn.execute(
        text("SELECT relrowsecurity FROM pg_class WHERE oid = 'kpi_values'::regclass")
    ).scalar()
    assert rls_enabled is True, 'kpi_values must carry the company-isolation RLS protection'


def test_kpi_values_enforces_closed_status_and_null_rule(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)
    document_id = _seed_document(conn, kpi_db.company_id)
    version_id = _seed_version(conn, kpi_db.company_id, document_id)

    # value may be NULL only with computation_status = needs_review.
    _seed_kpi(
        conn,
        kpi_db.company_id,
        version_id,
        kpi_code='runway',
        value=None,
        computation_status='needs_review',
    )
    with pytest.raises(IntegrityError), conn.begin_nested():
        _seed_kpi(
            conn,
            kpi_db.company_id,
            version_id,
            kpi_code='burn_rate',
            value=None,
            computation_status='computed',
        )
    with pytest.raises(IntegrityError), conn.begin_nested():
        _seed_kpi(
            conn,
            kpi_db.company_id,
            version_id,
            kpi_code='dso',
            computation_status='draft',
        )


# ---------------------------------------------------------------------------
# schema: kpi_rebuild_state
# ---------------------------------------------------------------------------


def test_kpi_rebuild_state_schema_and_lifecycle(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    assert _constraint_definition(conn, 'kpi_rebuild_state', 'p') == (
        'PRIMARY KEY (computation_rule_version)'
    )

    # A fresh target version starts pending, then moves running -> complete.
    conn.execute(
        text(
            'INSERT INTO kpi_rebuild_state (computation_rule_version) '
            "VALUES ('test-rule-lifecycle')"
        )
    )
    state = conn.execute(
        text(
            'SELECT state FROM kpi_rebuild_state '
            "WHERE computation_rule_version = 'test-rule-lifecycle'"
        )
    ).scalar()
    assert state == 'pending'

    conn.execute(
        text(
            "UPDATE kpi_rebuild_state SET state = 'running' "
            "WHERE computation_rule_version = 'test-rule-lifecycle'"
        )
    )
    conn.execute(
        text(
            "UPDATE kpi_rebuild_state SET state = 'complete' "
            "WHERE computation_rule_version = 'test-rule-lifecycle'"
        )
    )
    with pytest.raises(IntegrityError), conn.begin_nested():
        conn.execute(
            text(
                'INSERT INTO kpi_rebuild_state (computation_rule_version, state) '
                "VALUES ('test-rule-bad', 'finished')"
            )
        )


# ---------------------------------------------------------------------------
# view: final > newer selection
# ---------------------------------------------------------------------------


def test_kpi_current_selects_final_over_newer_draft(kpi_db: SimpleNamespace) -> None:
    """Final beats draft even when the draft document is the newer one."""
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)

    draft_doc = _seed_document(conn, kpi_db.company_id, status='draft')
    draft_version = _seed_version(
        conn,
        kpi_db.company_id,
        draft_doc,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    _seed_kpi(conn, kpi_db.company_id, draft_version)

    final_doc = _seed_document(conn, kpi_db.company_id, status='final')
    final_version = _seed_version(
        conn,
        kpi_db.company_id,
        final_doc,
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    _seed_kpi(conn, kpi_db.company_id, final_version)

    rows = _view_rows(conn, kpi_db.company_id)
    # Both documents cite the same figure, so there is no conflict to keep:
    # only the final document's row survives selection.
    assert len(rows) == 1
    assert str(rows[0].document_version_id) == final_version
    assert rows[0].is_selected is True
    assert rows[0].conflict_marker is None


def test_kpi_current_prefers_newer_final_over_older_final(kpi_db: SimpleNamespace) -> None:
    """Among final documents the newer version wins, but both rows persist."""
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)

    older_doc = _seed_document(conn, kpi_db.company_id, status='final')
    older_version = _seed_version(
        conn,
        kpi_db.company_id,
        older_doc,
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    _seed_kpi(conn, kpi_db.company_id, older_version, value='90.00')

    newer_doc = _seed_document(conn, kpi_db.company_id, status='final')
    newer_version = _seed_version(
        conn,
        kpi_db.company_id,
        newer_doc,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    _seed_kpi(conn, kpi_db.company_id, newer_version, value='100.00')

    rows = _view_rows(conn, kpi_db.company_id)
    assert len(rows) == 2, 'a real cross-document conflict keeps both cited rows'
    by_version = {str(row.document_version_id): row for row in rows}
    assert by_version[newer_version].is_selected is True
    assert by_version[older_version].is_selected is False
    # Both participants share one stable marker for UI grouping.
    assert by_version[newer_version].conflict_marker == 'revenue|2026-09'
    assert by_version[older_version].conflict_marker == 'revenue|2026-09'
    assert Decimal(by_version[newer_version].value) == Decimal('100.00')
    assert Decimal(by_version[older_version].value) == Decimal('90.00')


def test_kpi_current_keeps_draft_and_final_with_different_numbers(
    kpi_db: SimpleNamespace,
) -> None:
    """R28: draft and final disagree -> final is chosen, both are cited."""
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)

    draft_doc = _seed_document(conn, kpi_db.company_id, status='draft')
    draft_version = _seed_version(
        conn,
        kpi_db.company_id,
        draft_doc,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    _seed_kpi(conn, kpi_db.company_id, draft_version, value='90.00')

    final_doc = _seed_document(conn, kpi_db.company_id, status='final')
    final_version = _seed_version(
        conn,
        kpi_db.company_id,
        final_doc,
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    _seed_kpi(conn, kpi_db.company_id, final_version, value='100.00')

    rows = _view_rows(conn, kpi_db.company_id)
    assert len(rows) == 2
    by_version = {str(row.document_version_id): row for row in rows}
    # Final beats the newer draft for the chosen value.
    assert by_version[final_version].is_selected is True
    assert by_version[draft_version].is_selected is False
    assert by_version[final_version].conflict_marker == by_version[draft_version].conflict_marker


def test_kpi_current_returns_single_row_when_documents_agree(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)

    first_doc = _seed_document(conn, kpi_db.company_id, status='final')
    first_version = _seed_version(
        conn,
        kpi_db.company_id,
        first_doc,
        created_at=datetime.now(UTC) - timedelta(days=9),
    )
    _seed_kpi(conn, kpi_db.company_id, first_version, value='100.00')

    second_doc = _seed_document(conn, kpi_db.company_id, status='final')
    second_version = _seed_version(
        conn,
        kpi_db.company_id,
        second_doc,
        created_at=datetime.now(UTC) - timedelta(days=3),
    )
    _seed_kpi(conn, kpi_db.company_id, second_version, value='100.00')

    rows = _view_rows(conn, kpi_db.company_id)
    assert len(rows) == 1, 'identical figures from two documents are not a conflict'
    assert str(rows[0].document_version_id) == second_version
    assert rows[0].conflict_marker is None


def test_kpi_current_treats_different_currencies_as_conflict(
    kpi_db: SimpleNamespace,
) -> None:
    """100 USD and 100 EUR are different numbers: both cited rows persist."""
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)

    usd_doc = _seed_document(conn, kpi_db.company_id, status='final')
    usd_version = _seed_version(
        conn,
        kpi_db.company_id,
        usd_doc,
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    _seed_kpi(conn, kpi_db.company_id, usd_version, currency='USD', units='usd')

    eur_doc = _seed_document(conn, kpi_db.company_id, status='final')
    eur_version = _seed_version(
        conn,
        kpi_db.company_id,
        eur_doc,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    _seed_kpi(conn, kpi_db.company_id, eur_version, currency='EUR', units='eur')

    rows = _view_rows(conn, kpi_db.company_id)
    assert len(rows) == 2, 'equal values in different currencies still conflict'
    by_version = {str(row.document_version_id): row for row in rows}
    assert by_version[eur_version].is_selected is True
    assert by_version[usd_version].is_selected is False
    assert by_version[usd_version].conflict_marker == 'revenue|2026-09'


# ---------------------------------------------------------------------------
# view: supersession is history only
# ---------------------------------------------------------------------------


def test_kpi_current_excludes_superseded_history(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    _seed_company(conn, kpi_db.company_id)
    document_id = _seed_document(conn, kpi_db.company_id, status='final')

    old_version = _seed_version(
        conn,
        kpi_db.company_id,
        document_id,
        version=1,
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    new_version = _seed_version(
        conn,
        kpi_db.company_id,
        document_id,
        version=2,
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    _seed_kpi(conn, kpi_db.company_id, old_version, value='80.00', superseded_by=new_version)
    _seed_kpi(conn, kpi_db.company_id, new_version, value='95.00')

    rows = _view_rows(conn, kpi_db.company_id)
    assert len(rows) == 1, 'a superseded row is history, not current'
    assert str(rows[0].document_version_id) == new_version
    assert rows[0].is_selected is True

    # History itself is preserved in kpi_values until retention removes it.
    stored = conn.execute(
        text('SELECT COUNT(*) FROM kpi_values WHERE company_id = :company_id'),
        {'company_id': kpi_db.company_id},
    ).scalar()
    assert stored == 2


# ---------------------------------------------------------------------------
# view: retention
# ---------------------------------------------------------------------------


def test_kpi_current_honours_version_retention(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    version_retention_days, _ = _retention_defaults()
    _seed_company(conn, kpi_db.company_id)

    aged_doc = _seed_document(conn, kpi_db.company_id, status='final')
    aged_version = _seed_version(
        conn,
        kpi_db.company_id,
        aged_doc,
        created_at=datetime.now(UTC) - timedelta(days=version_retention_days + 5),
    )
    _seed_kpi(conn, kpi_db.company_id, aged_version)

    recent_doc = _seed_document(conn, kpi_db.company_id, status='final')
    recent_version = _seed_version(
        conn,
        kpi_db.company_id,
        recent_doc,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    _seed_kpi(conn, kpi_db.company_id, recent_version)

    rows = _view_rows(conn, kpi_db.company_id)
    assert [str(row.document_version_id) for row in rows] == [recent_version]

    # The session override tightens the window without a migration.
    conn.execute(text("SELECT set_config('app.version_retention_days', '0', false)"))
    try:
        assert _view_rows(conn, kpi_db.company_id) == []
    finally:
        conn.execute(text('RESET app.version_retention_days'))
    assert [str(row.document_version_id) for row in _view_rows(conn, kpi_db.company_id)] == [
        recent_version
    ]


def test_kpi_current_honours_deleted_retention(kpi_db: SimpleNamespace) -> None:
    conn = kpi_db.conn
    _, deleted_retention_days = _retention_defaults()
    _seed_company(conn, kpi_db.company_id)

    # One KPI code per document so selection groups stay independent and the
    # retention filter is observable row by row.
    active_doc = _seed_document(conn, kpi_db.company_id, status='final')
    active_version = _seed_version(conn, kpi_db.company_id, active_doc)
    _seed_kpi(conn, kpi_db.company_id, active_version, kpi_code='revenue')

    # Soft-deleted inside the retention window: still restorable, still shown.
    recycle_doc = _seed_document(
        conn,
        kpi_db.company_id,
        status='final',
        deleted_at=datetime.now(UTC) - timedelta(days=1),
    )
    recycle_version = _seed_version(conn, kpi_db.company_id, recycle_doc)
    _seed_kpi(conn, kpi_db.company_id, recycle_version, kpi_code='gross_margin')

    # Soft-deleted past the retention window: the rows go away.
    expired_doc = _seed_document(
        conn,
        kpi_db.company_id,
        status='deleted',
        deleted_at=datetime.now(UTC) - timedelta(days=deleted_retention_days + 1),
    )
    expired_version = _seed_version(conn, kpi_db.company_id, expired_doc)
    _seed_kpi(conn, kpi_db.company_id, expired_version, kpi_code='net_margin')

    rows = _view_rows(conn, kpi_db.company_id)
    assert sorted(str(row.document_version_id) for row in rows) == sorted(
        [active_version, recycle_version]
    )

    # A zero-day session override hides every soft-deleted document at once.
    conn.execute(text("SELECT set_config('app.deleted_retention_days', '0', false)"))
    try:
        rows = _view_rows(conn, kpi_db.company_id)
        assert [str(row.document_version_id) for row in rows] == [active_version]
    finally:
        conn.execute(text('RESET app.deleted_retention_days'))
