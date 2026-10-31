"""Auto-extracted helper for PostgresDocumentTableRepository._list."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_table_repository_shared import (
    _RETURNING,
    _TABLE,
    _company,
    _is_table,
    _matches,
    _row_to_table,
)

if TYPE_CHECKING:
    import builtins

    from finsight.domain.entities.document_table import DocumentTable


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _list(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> builtins.list[DocumentTable]:
    company = _company(company_id)
    if company_id is None and kwargs.get('company_id') is not None:
        company = _company(kwargs.pop('company_id'))
    elif company_id is None and kwargs.get('company') is not None:
        company = _company(kwargs.pop('company'))

    values = list(args)
    for value in values:
        if isinstance(value, dict):
            kwargs = {**value, **kwargs}
    scalar_values = [v for v in values if not isinstance(v, dict)]

    version_id = kwargs.pop(
        'version_id',
        kwargs.pop(
            'version', kwargs.pop('document_version', kwargs.pop('document_version_id', None))
        ),
    )
    version_ids = kwargs.pop('version_ids', kwargs.pop('versions', None))
    document_id = kwargs.pop('document_id', kwargs.pop('document', kwargs.pop('doc_id', None)))
    document_ids = kwargs.pop('document_ids', kwargs.pop('documents', None))
    page = kwargs.pop('page', kwargs.pop('page_number', kwargs.pop('page_from', None)))
    pages = kwargs.pop('pages', kwargs.pop('page_numbers', None))
    table_id = kwargs.pop('table_id', kwargs.pop('table', kwargs.pop('tableId', None)))
    table_ids = kwargs.pop('table_ids', kwargs.pop('tables', None))
    if isinstance(table_ids, (list, tuple)) and table_ids and _is_table(table_ids[0]):
        table_ids = None
    needs_review = kwargs.pop('needs_review', kwargs.pop('review', None))
    is_active = kwargs.pop('is_active', None)
    include_inactive = kwargs.pop('include_inactive', kwargs.pop('includeInactive', False))
    limit = kwargs.pop('limit', kwargs.pop('top_k', None))

    if version_id is None:
        for value in list(scalar_values):
            if isinstance(value, str):
                version_id = value
                scalar_values.remove(value)
                break
    if page is None:
        for value in list(scalar_values):
            if isinstance(value, int) and not isinstance(value, bool):
                page = value
                scalar_values.remove(value)
                break
    if table_id is None:
        for value in list(scalar_values):
            if isinstance(value, str):
                table_id = value
                scalar_values.remove(value)
                break

    versions_set = []
    if version_id is not None:
        versions_set.append(version_id)
    if version_ids is not None:
        versions_set.extend(
            list(version_ids) if isinstance(version_ids, (list, tuple, set)) else [version_ids]
        )
    pages_set = []
    if page is not None:
        pages_set.append(page)
    if pages is not None:
        pages_set.extend(list(pages) if isinstance(pages, (list, tuple, set)) else [pages])
    table_ids_set = None
    if table_ids is not None:
        table_ids_set = (
            list(table_ids) if isinstance(table_ids, (list, tuple, set)) else [table_ids]
        )

    filters: dict[str, Any] = {
        'version_id': version_id,
        'version_ids': versions_set if versions_set else None,
        'document_id': document_id,
        'document_ids': [document_id]
        if document_ids is None and document_id is not None
        else (
            (list(document_ids) if isinstance(document_ids, (list, tuple, set)) else [document_ids])
            if document_ids is not None
            else None
        ),
        'page': page if len(pages_set) <= 1 else None,
        'pages': pages_set if pages_set else None,
        'table_id': table_id,
        'table_ids': table_ids_set,
        'needs_review': needs_review,
        'is_active': is_active,
        'include_inactive': bool(include_inactive),
    }
    if versions_set and version_id is None:
        filters['version_ids'] = versions_set
        filters['version_id'] = None

    if self._session is None:
        store = self._memory.get(company, {})
        rows = [r for r in store.values() if _matches(r, filters)]
        if filters['version_ids'] and not filters['version_id']:
            rows = [
                r for r in rows if str(r.version_id) in {str(x) for x in filters['version_ids']}
            ]
        if limit is not None:
            rows = rows[: int(str(limit))]
        return rows

    await self._set_rls_context(company)
    params: dict[str, Any] = {'company_id': company}
    sql = f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id'
    if filters['version_id'] is not None:
        sql += ' AND version_id = :version_id'
        params['version_id'] = str(filters['version_id'])
    if filters['version_ids']:
        sql += ' AND version_id = ANY(:version_ids)'
        params['version_ids'] = [str(x) for x in filters['version_ids']]
    if filters['document_id'] is not None:
        sql += ' AND document_id::text = :document_id'
        params['document_id'] = str(filters['document_id'])
    if filters['page'] is not None:
        sql += ' AND page_number = :page_number'
        params['page_number'] = filters['page']
    if filters['pages']:
        sql += ' AND page_number = ANY(:pages)'
        params['pages'] = [int(x) if str(x).isdigit() else x for x in filters['pages']]
    if filters['table_id'] is not None:
        sql += ' AND table_id = :table_id'
        params['table_id'] = str(filters['table_id'])
    if filters['needs_review'] is not None:
        sql += ' AND needs_review = :needs_review'
        params['needs_review'] = bool(filters['needs_review'])
    if filters['is_active'] is not None:
        sql += ' AND is_active = :is_active'
        params['is_active'] = bool(filters['is_active'])
    elif not filters['include_inactive']:
        sql += ' AND is_active = TRUE'
    sql += ' ORDER BY created_at ASC, id ASC'
    if limit is not None:
        sql += ' LIMIT :limit'
        params['limit'] = int(str(limit))
    result = await self._execute(sql, params)
    rows = [r for r in (_row_to_table(x) for x in await self._fetchall(result)) if r is not None]
    return [r for r in rows if r is not None]
