"""Display-label precedence for KPI rows (issue #375).

``Updating`` is injected from staleness, ``Estimated`` from the computation
status and ``Draft`` from the source document version. Plain final figures have
no label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.value_objects.computation_status import ComputationStatus

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from finsight.domain.ports.kpi_repository import KpiRow


def apply_display_labels(
    rows: Sequence[KpiRow],
    *,
    document_statuses: Mapping[str, str] | None = None,
    updating: bool | Collection[str] = False,
) -> list[KpiRow]:
    """Return rows labelled with ``Updating > Estimated > Draft > null``."""
    statuses = {
        str(version): str(status).strip().lower()
        for version, status in (document_statuses or {}).items()
    }
    codes = None if isinstance(updating, bool) else {str(code) for code in updating}
    return [_labelled(row, statuses, updating, codes) for row in rows]


def _labelled(
    row: KpiRow,
    statuses: Mapping[str, str],
    updating: bool | Collection[str],
    codes: set[str] | None,
) -> KpiRow:
    labelled = dict(row)
    version = str(labelled.get('document_version_id', ''))
    label = 'Draft' if statuses.get(version) == 'draft' else None
    if _is_estimated(labelled):
        label = 'Estimated'
    if updating is True or (codes is not None and labelled.get('kpi_code') in codes):
        label = 'Updating'
    labelled['display_label'] = label
    return labelled


def _is_estimated(row: dict[str, Any]) -> bool:
    return (
        row.get('computation_status') == ComputationStatus.ESTIMATED
        or row.get('estimation_method') is not None
    )


__all__ = ['apply_display_labels']
