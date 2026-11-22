"""Private in-memory helpers for :class:`DashboardLayoutRepository`.

They mirror ``dashboard_layout_get`` and ``dashboard_layout_save`` from
migration 0009 so the shared contract suite runs without a database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.dashboard_layout_repository import LayoutConflictError, LayoutRecord

from . import _dashboard_layout_repository_layout as layout

if TYPE_CHECKING:
    from finsight.adapters.repositories._dashboard_layout_repository_layout import _LayoutContext

LayoutMemory = dict[tuple[str, str], LayoutRecord]


def stored_record(
    memory: LayoutMemory, key: tuple[str, str], context: _LayoutContext
) -> LayoutRecord:
    """Return the stored layout filtered for the caller, or the config default."""
    stored = memory.get(key)
    if stored is None:
        return layout.default_record(context.config, context.visible)
    filtered = layout.resolve_layout(stored, context.config, context.visible)
    return layout.record(
        filtered['kpi_codes'], filtered['charts'], stored['version'], stored['updated_at']
    )


def put_record(
    memory: LayoutMemory,
    key: tuple[str, str],
    incoming: Any,
    expected_version: int,
    context: _LayoutContext,
) -> LayoutRecord:
    """Apply the optimistic conditional update, incrementing on success."""
    stored = memory.get(key)
    current_version = 0 if stored is None else int(stored['version'])
    if current_version != expected_version:
        raise LayoutConflictError(stored_record(memory, key, context))
    filtered = layout.resolve_layout(incoming, context.config, context.visible)
    saved = layout.record(
        filtered['kpi_codes'], filtered['charts'], current_version + 1, datetime.now(UTC)
    )
    memory[key] = saved
    return saved
