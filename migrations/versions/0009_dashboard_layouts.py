"""phase 2.2-06: dashboard_layouts table and its read/save primitives

Revision ID: 0009_dashboard_layouts
Revises: 0008_kpi_store
Create Date: 2026-11-22 00:00:00.000000

The saved-layout store of phase2_spec.md section 3.4: one company/user-keyed
table holding only identifiers and positions, plus the database primitives
the layout repository calls.  Reads return the config default on a miss
without writing; saves are optimistic (the loaded version must match, then
increments).  The caller supplies the visible id set - the intersection of
role permissions and the config catalogue - so ids that are unpermitted or
unknown to config are dropped on both paths.  No second store path and no
``layout_store`` switch exist (ADR-0011).

The default layout comes from the active profile at migration time, the same
way ``migrations/env.py`` and revision 0008 resolve their values.  The
documented env-only migration path (scripts/run_migration.py sets only
VECTOR_DB_*) cannot resolve the full profile, so the documented schema
defaults are baked with a warning there; a profile that does load but has no
dashboard section fails loudly.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import TYPE_CHECKING, Any

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

_LOGGER = logging.getLogger('alembic.versions.0009_dashboard_layouts')

# The config loader import can fail during migration runs that only carry
# VECTOR_DB_* env vars; the documented schema defaults are baked instead.
try:
    from finsight.core.config import load_config
except Exception as exc:  # import failure must not break the migration
    load_config = None  # type: ignore[assignment]
    _LOGGER.warning('Config loader unavailable (%s); baking schema defaults', exc)

revision: str = '0009_dashboard_layouts'
down_revision: str | None = '0008_kpi_store'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Documented defaults from config/schema.yaml (dashboard.default_layout),
# used only when the full profile cannot be resolved; see _default_layout().
_DEFAULT_LAYOUT: dict[str, Any] = {
    'kpi_codes': [
        'revenue',
        'gross_margin',
        'net_margin',
        'operating_expenses',
        'cash_flow',
        'burn_rate',
    ],
    'charts': [
        {'chart_id': 'revenue_trend', 'span': 'full'},
        {'chart_id': 'margin_trend', 'span': 'half'},
    ],
}


def _default_layout() -> dict[str, Any]:
    """Resolve ``dashboard.default_layout`` as env.py/0008 resolve their values.

    The production migration path supplies only VECTOR_DB_* variables, so the
    full profile cannot be resolved there; the documented schema defaults are
    baked with a warning.  A profile that loads but has no dashboard section
    is broken and fails loudly instead of falling back silently.
    """
    if load_config is not None:
        try:
            config = load_config()
        except Exception as exc:  # env-only migration path
            _LOGGER.warning('App config unusable (%s); baking schema defaults', exc)
        else:
            if config.dashboard is None:
                raise RuntimeError('dashboard config section is required by the layout migration')
            default = config.dashboard.default_layout
            return {
                'kpi_codes': list(default.kpi_codes),
                'charts': [
                    {'chart_id': chart.chart_id, 'span': chart.span} for chart in default.charts
                ],
            }
    return copy.deepcopy(_DEFAULT_LAYOUT)


def _json_literal(value: object) -> str:
    """Embed a JSON value safely in a SQL single-quoted literal."""
    return json.dumps(value).replace("'", "''")


def upgrade() -> None:
    """Create the saved-layout table, its isolation policy and read/save functions."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_layouts (
            company_id       UUID        NOT NULL,
            user_id          UUID        NOT NULL,
            contract_version INTEGER     NOT NULL,
            kpi_codes        JSONB       NOT NULL,
            charts           JSONB       NOT NULL,
            version          INTEGER     NOT NULL,
            updated_at       TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (company_id, user_id)
        )
        """
    )

    # Company isolation, same policy shape as every other company-scoped table.
    op.execute('ALTER TABLE dashboard_layouts ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE dashboard_layouts FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS dashboard_layouts_company_isolation ON dashboard_layouts')
    op.execute(
        """
        CREATE POLICY dashboard_layouts_company_isolation ON dashboard_layouts
            USING (company_id = current_setting('app.company_id', true)::uuid)
            WITH CHECK (company_id = current_setting('app.company_id', true)::uuid)
        """
    )

    # Keep identifier order, dropping ids outside the caller's visible set.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION _dashboard_layout_filter_ids(
            p_kpi_codes JSONB,
            p_charts JSONB,
            p_visible_ids JSONB
        ) RETURNS JSONB
        LANGUAGE sql IMMUTABLE
        AS $function$
            SELECT jsonb_build_object(
                'kpi_codes', COALESCE(
                    (SELECT jsonb_agg(item.code ORDER BY item.position)
                     FROM jsonb_array_elements_text(p_kpi_codes) WITH ORDINALITY
                         AS item(code, position)
                     WHERE p_visible_ids -> 'kpi_codes' ? item.code),
                    '[]'::jsonb
                ),
                'charts', COALESCE(
                    (SELECT jsonb_agg(item.chart ORDER BY item.position)
                     FROM jsonb_array_elements(p_charts) WITH ORDINALITY
                         AS item(chart, position)
                     WHERE p_visible_ids -> 'chart_ids' ? (item.chart ->> 'chart_id')),
                    '[]'::jsonb
                )
            )
        $function$
        """
    )

    default_literal = _json_literal(_default_layout())

    # A miss returns the config default with version 0 and no stored row.
    # A saved layout is filtered on the way out, never mutated by a read.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION dashboard_layout_get(
            p_company_id UUID,
            p_user_id UUID,
            p_visible_ids JSONB
        ) RETURNS TABLE (
            contract_version INTEGER,
            kpi_codes JSONB,
            charts JSONB,
            version INTEGER,
            updated_at TIMESTAMPTZ
        )
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            v_saved dashboard_layouts%ROWTYPE;
            v_default JSONB := '{default_literal}'::jsonb;
            v_visible JSONB;
        BEGIN
            SELECT * INTO v_saved
            FROM dashboard_layouts AS dl
            WHERE dl.company_id = p_company_id AND dl.user_id = p_user_id;

            IF NOT FOUND THEN
                v_visible := _dashboard_layout_filter_ids(
                    v_default -> 'kpi_codes', v_default -> 'charts', p_visible_ids);
                RETURN QUERY
                    SELECT 1, v_visible -> 'kpi_codes', v_visible -> 'charts',
                           0, NULL::TIMESTAMPTZ;
                RETURN;
            END IF;

            v_visible := _dashboard_layout_filter_ids(
                v_saved.kpi_codes, v_saved.charts, p_visible_ids);
            IF jsonb_array_length(v_visible -> 'kpi_codes') = 0
               AND jsonb_array_length(v_visible -> 'charts') = 0 THEN
                v_visible := _dashboard_layout_filter_ids(
                    v_default -> 'kpi_codes', v_default -> 'charts', p_visible_ids);
            END IF;

            RETURN QUERY
                SELECT 1, v_visible -> 'kpi_codes', v_visible -> 'charts',
                       v_saved.version, v_saved.updated_at;
        END
        $function$
        """
    )

    # Conditional update: the loaded version must match, then it increments.
    # Version 0 with no row is the first save; a stale or racing version
    # returns no row, which the handler maps to 409 with the current layout.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION dashboard_layout_save(
            p_company_id UUID,
            p_user_id UUID,
            p_expected_version INTEGER,
            p_kpi_codes JSONB,
            p_charts JSONB,
            p_visible_ids JSONB
        ) RETURNS TABLE (
            contract_version INTEGER,
            kpi_codes JSONB,
            charts JSONB,
            version INTEGER,
            updated_at TIMESTAMPTZ
        )
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            v_saved dashboard_layouts%ROWTYPE;
            v_default JSONB := '{default_literal}'::jsonb;
            v_visible JSONB;
        BEGIN
            v_visible := _dashboard_layout_filter_ids(
                p_kpi_codes, p_charts, p_visible_ids);
            IF jsonb_array_length(v_visible -> 'kpi_codes') = 0
               AND jsonb_array_length(v_visible -> 'charts') = 0 THEN
                v_visible := _dashboard_layout_filter_ids(
                    v_default -> 'kpi_codes', v_default -> 'charts', p_visible_ids);
            END IF;

            UPDATE dashboard_layouts AS dl
            SET kpi_codes = v_visible -> 'kpi_codes',
                charts = v_visible -> 'charts',
                version = dl.version + 1,
                updated_at = now()
            WHERE dl.company_id = p_company_id
              AND dl.user_id = p_user_id
              AND dl.version = p_expected_version
            RETURNING dl.* INTO v_saved;

            IF NOT FOUND AND p_expected_version = 0 THEN
                INSERT INTO dashboard_layouts AS dl
                    (company_id, user_id, contract_version, kpi_codes, charts, version, updated_at)
                VALUES (p_company_id, p_user_id, 1,
                        v_visible -> 'kpi_codes', v_visible -> 'charts', 1, now())
                ON CONFLICT (company_id, user_id) DO NOTHING
                RETURNING dl.* INTO v_saved;
            END IF;

            RETURN QUERY
                SELECT 1, v_saved.kpi_codes, v_saved.charts,
                       v_saved.version, v_saved.updated_at
                WHERE v_saved.company_id IS NOT NULL;
        END
        $function$
        """
    )


def downgrade() -> None:
    """Drop the saved-layout primitives, policy and table."""
    op.execute(
        'DROP FUNCTION IF EXISTS dashboard_layout_save(uuid, uuid, integer, jsonb, jsonb, jsonb)'
    )
    op.execute('DROP FUNCTION IF EXISTS dashboard_layout_get(uuid, uuid, jsonb)')
    op.execute('DROP FUNCTION IF EXISTS _dashboard_layout_filter_ids(jsonb, jsonb, jsonb)')
    op.execute('DROP POLICY IF EXISTS dashboard_layouts_company_isolation ON dashboard_layouts')
    op.execute('ALTER TABLE dashboard_layouts NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE dashboard_layouts DISABLE ROW LEVEL SECURITY')
    op.execute('DROP TABLE IF EXISTS dashboard_layouts')
