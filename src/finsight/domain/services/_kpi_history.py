"""Conflict and supersession markers for KPI rows (issue #375).

Cross-document rows with the same company, KPI and period stay visible with a
shared conflict marker. Same-document history is recorded separately as
supersession so it is never mistaken for a conflict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from finsight.domain.value_objects.computation_status import ComputationStatus

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from finsight.domain.ports.kpi_repository import KpiRow

_ACTIVE_STATUSES = (ComputationStatus.COMPUTED, ComputationStatus.ESTIMATED)


def mark_conflicts(rows: Sequence[KpiRow]) -> list[KpiRow]:
    """Mark rows from different documents that disagree on one KPI period."""
    result = [dict(row) for row in rows]
    groups: dict[tuple[str, ...], list[KpiRow]] = {}
    for row in result:
        row.setdefault('conflict_marker', None)
        if row.get('value') is None or row.get('superseded_by_document_version_id') is not None:
            continue
        if row.get('computation_status') not in _ACTIVE_STATUSES:
            continue
        key = (
            str(row.get('company_id', '')),
            str(row.get('kpi_code', '')),
            str(row.get('period', '')),
            str(row.get('chart_period', '')),
        )
        groups.setdefault(key, []).append(row)

    for group in groups.values():
        if len({str(row.get('document_version_id', '')) for row in group}) < 2:
            continue
        marker = f'{group[0]["kpi_code"]}|{group[0]["period"]}'
        for row in group:
            row['conflict_marker'] = marker
    return result


def mark_supersession(rows: Sequence[KpiRow], superseded_by: Mapping[str, str]) -> list[KpiRow]:
    """Apply same-document history as ``superseded_by_document_version_id``."""
    result: list[KpiRow] = []
    for row in rows:
        marked = dict(row)
        replacement = superseded_by.get(str(marked.get('document_version_id', '')))
        if replacement and marked.get('superseded_by_document_version_id') is None:
            marked['superseded_by_document_version_id'] = str(replacement)
        result.append(marked)
    return result


__all__ = ['mark_conflicts', 'mark_supersession']
