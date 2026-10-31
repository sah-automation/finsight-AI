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


async def _mark_inactive(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> int:
    company_id = kwargs.pop('company_id', kwargs.pop('company', company_id))
    values = list(args)
    if company_id is None and values and not isinstance(values[0], (list, tuple, set)):
        company_id = values.pop(0)
    company = _company(company_id)

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
    if table_ids is None and target_ids is not None:
        table_ids = target_ids
    exclude_ids = {
        str(x)
        for x in (
            exclude
            if isinstance(exclude, (list, tuple, set))
            else ([exclude] if exclude is not None else [])
        )
    }

    changed = 0
    if self._session is None:
        store = self._memory.get(company, {})
        for _rid, row in list(store.items()):
            affected = False
            if table_ids is not None:
                ids = [
                    str(x)
                    for x in (
                        table_ids if isinstance(table_ids, (list, tuple, set)) else [table_ids]
                    )
                ]
                if str(row.id) in ids or str(row.table_id) in ids:
                    affected = True
            if version_id is not None and str(row.version_id) == str(version_id):
                if str(row.id) not in exclude_ids and str(row.table_id) not in exclude_ids:
                    affected = True
            if document_id is not None and str(row.document_id) == str(document_id):
                affected = True
            if table_ids is None and version_id is None and document_id is None:
                affected = False
            if affected:
                row.is_active = False
                row.updated_at = _utcnow()
                changed += 1
        return changed

    await self._set_rls_context(company)
    clauses = []
    params: dict[str, Any] = {'company_id': company}
    if table_ids is not None:
        ids = [
            str(x)
            for x in (table_ids if isinstance(table_ids, (list, tuple, set)) else [table_ids])
        ]
        clauses.append('(id = ANY(:ids) OR table_id = ANY(:ids))')
        params['ids'] = ids
    if version_id is not None:
        clauses.append('version_id = :version_id')
        params['version_id'] = str(version_id)
    if document_id is not None:
        clauses.append('document_id::text = :document_id')
        params['document_id'] = str(document_id)
    if not clauses:
        return 0
    sql = (
        'UPDATE document_tables SET is_active = FALSE, updated_at = now() WHERE company_id = :company_id AND ('
        + ' OR '.join(clauses)
        + ')'
    )
    if exclude_ids and version_id is not None:
        sql += ' AND (table_id IS NULL OR table_id <> ALL(:exclude_ids)) AND (id::text <> ALL(:exclude_ids))'
        params['exclude_ids'] = list(exclude_ids)
    result = await self._execute(sql, params)
    rowcount = getattr(result, 'rowcount', None)
    if rowcount is None:
        rowcount = 0
    return int(rowcount or changed or 0)
