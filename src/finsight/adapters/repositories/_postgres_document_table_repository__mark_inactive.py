"""Auto-extracted helper for PostgresDocumentTableRepository._mark_inactive."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_table_repository_shared import (
    _company,
    _utcnow,
)

if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


def _pop_mark_filters(
    kwargs: dict[str, object],
) -> tuple[object, object, object, object, object]:
    version_id = kwargs.pop(
        'version_id',
        kwargs.pop(
            'version', kwargs.pop('document_version', kwargs.pop('document_version_id', None))
        ),
    )
    document_id = kwargs.pop('document_id', kwargs.pop('document', None))
    table_ids = kwargs.pop('table_ids', kwargs.pop('ids', kwargs.pop('id_list', None)))
    target_ids = kwargs.pop('target_ids', None)
    exclude = kwargs.pop(
        'exclude_table_ids',
        kwargs.pop('exclude_ids', kwargs.pop('keep', kwargs.pop('keep_table_ids', ()))),
    )
    return version_id, document_id, table_ids, target_ids, exclude


def _consume_mark_values(
    values: list[object],
    version_id: object,
    table_ids: object,
) -> tuple[object, object]:
    for value in list(values):
        if isinstance(value, (list, tuple, set)):
            if table_ids is None:
                table_ids = value
            values.remove(value)
            continue
        if version_id is None:
            version_id = value
            values.remove(value)
            continue
        if table_ids is None:
            table_ids = [value]
            values.remove(value)
    return version_id, table_ids


def _normalise_exclude_ids(exclude: object) -> set[str]:
    if isinstance(exclude, (list, tuple, set)):
        return {str(x) for x in exclude}
    if exclude is not None:
        return {str(exclude)}
    return set()


def _parse_mark_inactive_args(
    company_id: object,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> tuple[str, object, object, object, set[str]]:
    company_id = kwargs.pop('company_id', kwargs.pop('company', company_id))
    values = list(args)
    if company_id is None and values and not isinstance(values[0], (list, tuple, set)):
        company_id = values.pop(0)
    company = _company(company_id)
    version_id, document_id, table_ids, target_ids, exclude = _pop_mark_filters(kwargs)
    version_id, table_ids = _consume_mark_values(values, version_id, table_ids)
    if table_ids is None and target_ids is not None:
        table_ids = target_ids
    return company, version_id, document_id, table_ids, _normalise_exclude_ids(exclude)


def _mark_ids(table_ids: object) -> list[str]:
    if isinstance(table_ids, (list, tuple, set)):
        return [str(x) for x in table_ids]
    return [] if table_ids is None else [str(table_ids)]


def _mark_memory_affected(
    row: Any,
    ids: list[str],
    version_id: object,
    document_id: object,
    exclude_ids: set[str],
) -> bool:
    affected = False
    if ids and (str(row.id) in ids or str(row.table_id) in ids):
        affected = True
    if version_id is not None and str(row.version_id) == str(version_id):
        if str(row.id) not in exclude_ids and str(row.table_id) not in exclude_ids:
            affected = True
    if document_id is not None and str(row.document_id) == str(document_id):
        affected = True
    return affected


def _mark_inactive_memory(
    self: PostgresDocumentTableRepository,
    company: str,
    version_id: object,
    document_id: object,
    table_ids: object,
    exclude_ids: set[str],
) -> int:
    store = self._memory.get(company, {})
    ids = _mark_ids(table_ids)
    changed = 0
    for _rid, row in list(store.items()):
        if _mark_memory_affected(row, ids, version_id, document_id, exclude_ids):
            row.is_active = False
            row.updated_at = _utcnow()
            changed += 1
    return changed


def _build_mark_clauses(
    table_ids: object,
    version_id: object,
    document_id: object,
    params: dict[str, Any],
) -> list[str]:
    clauses: list[str] = []
    if table_ids is not None:
        params['ids'] = _mark_ids(table_ids)
        clauses.append('(id = ANY(:ids) OR table_id = ANY(:ids))')
    if version_id is not None:
        clauses.append('version_id = :version_id')
        params['version_id'] = str(version_id)
    if document_id is not None:
        clauses.append('document_id::text = :document_id')
        params['document_id'] = str(document_id)
    return clauses


async def _mark_inactive_sql(
    self: PostgresDocumentTableRepository,
    company: str,
    version_id: object,
    document_id: object,
    table_ids: object,
    exclude_ids: set[str],
) -> int:
    params: dict[str, Any] = {'company_id': company}
    clauses = _build_mark_clauses(table_ids, version_id, document_id, params)
    if not clauses:
        return 0
    sql = (
        'UPDATE document_tables SET is_active = FALSE, updated_at = now() '
        'WHERE company_id = :company_id AND (' + ' OR '.join(clauses) + ')'
    )
    if exclude_ids and version_id is not None:
        sql += (
            ' AND (table_id IS NULL OR table_id <> ALL(:exclude_ids)) '
            'AND (id::text <> ALL(:exclude_ids))'
        )
        params['exclude_ids'] = list(exclude_ids)
    result = await self._execute(sql, params)
    rowcount = getattr(result, 'rowcount', None)
    return int(rowcount or 0)


async def _mark_inactive(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> int:
    company, version_id, document_id, table_ids, exclude_ids = _parse_mark_inactive_args(
        company_id, args, kwargs
    )
    if self._session is None:
        return _mark_inactive_memory(self, company, version_id, document_id, table_ids, exclude_ids)
    await self._set_rls_context(company)
    return await _mark_inactive_sql(self, company, version_id, document_id, table_ids, exclude_ids)
