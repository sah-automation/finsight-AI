"""phase 2.2-05: kpi_values table, kpi_rebuild_state table, kpi_current view

Revision ID: 0008_kpi_store
Revises: 0007_slice6_document_tables
Create Date: 2026-11-22 00:00:00.000000

The KPI store of phase2_spec.md section 3.2: one ``kpi_values`` table (no
monthly partitioning), one ``kpi_rebuild_state`` gating table, and the
``kpi_current`` read view.  Retention windows are baked into the view from
the active configuration profile at migration time - the same way
``migrations/env.py`` resolves the database URL - and can be overridden per
session with the ``app.version_retention_days`` / ``app.deleted_retention_days``
settings without another migration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

_LOGGER = logging.getLogger('alembic.versions.0008_kpi_store')

# The config loader import can fail during migration runs that only carry
# database env vars; the documented schema defaults are baked instead.
try:
    from finsight.core.config import load_config
except Exception as exc:  # import failure must not break the migration
    load_config = None  # type: ignore[assignment]
    _LOGGER.warning('Config loader unavailable (%s); baking schema defaults', exc)

revision: str = '0008_kpi_store'
down_revision: str | None = '0007_slice6_document_tables'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Documented defaults from config/schema.yaml (documents section) used only
# when the config loader cannot answer; see _retention_defaults().
_DEFAULT_VERSION_RETENTION_DAYS = 365
_DEFAULT_DELETED_RETENTION_DAYS = 30


def _retention_defaults() -> tuple[int, int]:
    """Resolve ``(version_retention_days, deleted_retention_days)`` from config.

    Mirrors ``migrations/env.py``: the active profile is the source of truth,
    so each environment's ``kpi_current`` view honours its own configured
    retention.  When the config loader is unavailable the documented schema
    defaults are baked instead; either value can still be overridden at read
    time through the ``app.*`` session settings.
    """
    if load_config is not None:
        try:
            documents = load_config().documents
            if documents is not None:
                return (
                    int(documents.version_retention_days),
                    int(documents.deleted_retention_days),
                )
        except Exception as exc:
            _LOGGER.warning('Config unavailable (%s); baking schema defaults', exc)
    return _DEFAULT_VERSION_RETENTION_DAYS, _DEFAULT_DELETED_RETENTION_DAYS


def upgrade() -> None:
    """Create the Phase 2 KPI store."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS kpi_values (
            company_id                        UUID        NOT NULL,
            kpi_code                          TEXT        NOT NULL,
            period                            TEXT        NOT NULL,
            document_version_id               UUID        NOT NULL,
            chart_period                      TEXT        NOT NULL,
            period_start                      DATE        NOT NULL,
            chart_period_start                DATE        NOT NULL,
            currency                          TEXT        NOT NULL,
            units                             TEXT        NOT NULL,
            value                             NUMERIC     NULL,
            computation_status                TEXT        NOT NULL
                CHECK (computation_status IN ('computed', 'estimated', 'needs_review')),
            estimation_method                 TEXT        NULL,
            source_citations                  JSONB       NOT NULL,
            computation_rule_version          TEXT        NOT NULL,
            superseded_by_document_version_id UUID        NULL,
            created_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (company_id, kpi_code, period, document_version_id, chart_period),
            CONSTRAINT ck_kpi_values_value_needs_review
                CHECK (value IS NOT NULL OR computation_status = 'needs_review')
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS kpi_values_company_code_start '
        'ON kpi_values (company_id, kpi_code, period_start DESC)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS kpi_values_company_chart_start '
        'ON kpi_values (company_id, chart_period_start)'
    )

    # Company isolation, same policy shape as every other company-scoped table.
    op.execute('ALTER TABLE kpi_values ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE kpi_values FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS kpi_values_company_isolation ON kpi_values')
    op.execute(
        """
        CREATE POLICY kpi_values_company_isolation ON kpi_values
            USING (company_id = current_setting('app.company_id', true)::uuid)
            WITH CHECK (company_id = current_setting('app.company_id', true)::uuid)
        """
    )

    # Rebuild gating: a new computation_rule_version cannot activate until
    # its rebuild reaches 'complete' (ADR-0009, same gate pattern as
    # embedding changes).  Global, not company-scoped: no RLS.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS kpi_rebuild_state (
            computation_rule_version TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'pending'
                CHECK (state IN ('pending', 'running', 'complete')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    version_retention_days, deleted_retention_days = _retention_defaults()
    op.execute(
        f"""
        CREATE VIEW kpi_current AS
        WITH source_rows AS (
            SELECT
                kv.*,
                dv.document_id AS document_id,
                dv.created_at AS source_version_created_at,
                d.status AS document_status
            FROM kpi_values AS kv
            INNER JOIN document_versions AS dv
                ON dv.id = kv.document_version_id
               AND dv.company_id = kv.company_id
            INNER JOIN documents AS d
                ON d.id = dv.document_id
               AND d.company_id = kv.company_id
            WHERE
                -- version_retention_days: rows go away with their source version.
                dv.created_at >= now() - make_interval(days => COALESCE(
                    NULLIF(current_setting('app.version_retention_days', true), '')::integer,
                    {version_retention_days}))
                -- deleted_retention_days: a soft-deleted document's rows go away
                -- once its deletion retention expires (restore brings them back).
                AND (
                    d.deleted_at IS NULL
                    OR d.deleted_at >= now() - make_interval(days => COALESCE(
                        NULLIF(current_setting('app.deleted_retention_days', true), '')::integer,
                        {deleted_retention_days}))
                )
                -- Supersession is history only: never a current candidate.
                AND kv.superseded_by_document_version_id IS NULL
        ),
        ranked_rows AS (
            SELECT
                sr.*,
                row_number() OVER (
                    PARTITION BY sr.company_id, sr.kpi_code, sr.period, sr.chart_period
                    ORDER BY
                        CASE WHEN sr.document_status = 'draft' THEN 0 ELSE 1 END DESC,
                        sr.source_version_created_at DESC,
                        sr.updated_at DESC,
                        sr.document_version_id DESC
                ) AS selection_rank
            FROM source_rows AS sr
        ),
        -- A real conflict is derived on read: different documents still show
        -- different numbers for the same company, KPI and period (ADR-0009).
        -- Same-document rows never conflict; they are supersession history.
        conflicted_groups AS (
            SELECT
                a.company_id,
                a.kpi_code,
                a.period
            FROM ranked_rows AS a
            INNER JOIN ranked_rows AS b
                ON b.company_id = a.company_id
               AND b.kpi_code = a.kpi_code
               AND b.period = a.period
               AND b.document_id <> a.document_id
               AND a.value IS NOT NULL
               AND b.value IS NOT NULL
               AND a.value <> b.value
            GROUP BY a.company_id, a.kpi_code, a.period
        )
        SELECT
            rr.company_id,
            rr.kpi_code,
            rr.period,
            rr.document_version_id,
            rr.chart_period,
            rr.period_start,
            rr.chart_period_start,
            rr.currency,
            rr.units,
            rr.value,
            rr.computation_status,
            rr.estimation_method,
            rr.source_citations,
            rr.computation_rule_version,
            rr.superseded_by_document_version_id,
            rr.created_at,
            rr.updated_at,
            rr.document_status,
            CASE
                WHEN cf.company_id IS NULL THEN NULL
                ELSE rr.kpi_code || '|' || rr.period
            END AS conflict_marker,
            rr.selection_rank = 1 AS is_selected
        FROM ranked_rows AS rr
        LEFT JOIN conflicted_groups AS cf
            ON cf.company_id = rr.company_id
           AND cf.kpi_code = rr.kpi_code
           AND cf.period = rr.period
        WHERE rr.selection_rank = 1
           OR cf.company_id IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop the Phase 2 KPI store."""
    op.execute('DROP VIEW IF EXISTS kpi_current')
    op.execute('DROP TABLE IF EXISTS kpi_rebuild_state')
    op.execute('DROP POLICY IF EXISTS kpi_values_company_isolation ON kpi_values')
    op.execute('ALTER TABLE kpi_values NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE kpi_values DISABLE ROW LEVEL SECURITY')
    op.execute('DROP TABLE IF EXISTS kpi_values')
