"""Conflict and supersession markers for KPI rows (issue #375).

Cross-document rows with the same company, KPI and declared period but
different figures stay visible with a shared conflict marker. Same-document
history is recorded separately as supersession so it is never mistaken for a
conflict; callers must apply that history before detecting conflicts.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from finsight.domain.value_objects.computation_status import ComputationStatus

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from finsight.domain.ports.kpi_repository import KpiRow

_ACTIVE_STATUSES = (ComputationStatus.COMPUTED, ComputationStatus.ESTIMATED)


def mark_conflicts(rows: Sequence[KpiRow]) -> list[KpiRow]:
    """Mark rows from different documents that disagree on one KPI period."""
    result = [dict(row) for row in rows]
    groups: dict[tuple[str, str, str], list[KpiRow]] = {}
    for row in result:
        row.setdefault('conflict_marker', None)
        if _eligible(row):
            groups.setdefault(_key(row), []).append(row)
    for group in groups.values():
        if _conflicted(group):
            marker = f'{group[0]["kpi_code"]}|{group[0]["period"]}'
            for row in group:
                row['conflict_marker'] = marker
    return result


def _eligible(row: KpiRow) -> bool:
    return (
        row.get('value') is not None
        and row.get('superseded_by_document_version_id') is None
        and row.get('computation_status') in _ACTIVE_STATUSES
    )


def _key(row: KpiRow) -> tuple[str, str, str]:
    return (
        str(row.get('company_id', '')),
        str(row.get('kpi_code', '')),
        str(row.get('period', '')),
    )


def _conflicted(group: list[KpiRow]) -> bool:
    versions = {str(row.get('document_version_id', '')) for row in group}
    if len(versions) < 2:
        return False
    return len({_figure(row) for row in group}) > 1


def _figure(row: KpiRow) -> object:
    try:
        return Decimal(str(row.get('value')))
    except (InvalidOperation, TypeError, ValueError):
        return str(row.get('value'))


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
