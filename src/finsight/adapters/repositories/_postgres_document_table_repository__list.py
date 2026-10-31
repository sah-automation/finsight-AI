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


def _merge_list_args(
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> tuple[list[object], dict[str, object]]:
    values = list(args)
    for value in values:
        if isinstance(value, dict):
            kwargs = {**value, **kwargs}
    scalar_values = [v for v in values if not isinstance(v, dict)]
    return scalar_values, kwargs


def _pop_list_scope_filters(kwargs: dict[str, object]) -> dict[str, Any]:
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
    return {
        'version_id': version_id,
        'version_ids': version_ids,
        'document_id': document_id,
        'document_ids': document_ids,
        'page': page,
        'pages': pages,
    }


def _pop_list_remaining_filters(kwargs: dict[str, object]) -> dict[str, Any]:
    table_id = kwargs.pop('table_id', kwargs.pop('table', kwargs.pop('tableId', None)))
    table_ids = kwargs.pop('table_ids', kwargs.pop('tables', None))
    if isinstance(table_ids, (list, tuple)) and table_ids and _is_table(table_ids[0]):
        table_ids = None
    needs_review = kwargs.pop('needs_review', kwargs.pop('review', None))
    is_active = kwargs.pop('is_active', None)
    include_inactive = kwargs.pop('include_inactive', kwargs.pop('includeInactive', False))
    limit = kwargs.pop('limit', kwargs.pop('top_k', None))
    return {
        'table_id': table_id,
        'table_ids': table_ids,
        'needs_review': needs_review,
        'is_active': is_active,
        'include_inactive': include_inactive,
        'limit': limit,
    }


def _pop_list_filters(kwargs: dict[str, object]) -> dict[str, Any]:
    return {**_pop_list_scope_filters(kwargs), **_pop_list_remaining_filters(kwargs)}


def _consume_scalar_args(scalar_values: list[object], raw: dict[str, Any]) -> None:
    if raw['version_id'] is None:
        for value in list(scalar_values):
            if isinstance(value, str):
                raw['version_id'] = value
                scalar_values.remove(value)
                break
    if raw['page'] is None:
        for value in list(scalar_values):
            if isinstance(value, int) and not isinstance(value, bool):
                raw['page'] = value
                scalar_values.remove(value)
                break
    if raw['table_id'] is None:
        for value in list(scalar_values):
            if isinstance(value, str):
                raw['table_id'] = value
                scalar_values.remove(value)
                break


def _as_list_or_single(value: object) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _document_filter_ids(document_id: object, document_ids: object) -> list[Any] | None:
    if document_ids is None:
        return [document_id] if document_id is not None else None
    return _as_list_or_single(document_ids)


def _finalise_list_filters(raw: dict[str, Any]) -> dict[str, Any]:
    versions_set: list[Any] = []
    if raw['version_id'] is not None:
        versions_set.append(raw['version_id'])
    if raw['version_ids'] is not None:
        versions_set.extend(_as_list_or_single(raw['version_ids']))
    pages_set: list[Any] = []
    if raw['page'] is not None:
        pages_set.append(raw['page'])
    if raw['pages'] is not None:
        pages_set.extend(_as_list_or_single(raw['pages']))
    table_ids_set = _as_list_or_single(raw['table_ids']) if raw['table_ids'] is not None else None
    filters: dict[str, Any] = {
        'version_id': raw['version_id'],
        'version_ids': versions_set if versions_set else None,
        'document_id': raw['document_id'],
        'document_ids': _document_filter_ids(raw['document_id'], raw['document_ids']),
        'page': raw['page'] if len(pages_set) <= 1 else None,
        'pages': pages_set if pages_set else None,
        'table_id': raw['table_id'],
        'table_ids': table_ids_set,
        'needs_review': raw['needs_review'],
        'is_active': raw['is_active'],
        'include_inactive': bool(raw['include_inactive']),
    }
    if versions_set and raw['version_id'] is None:
        filters['version_ids'] = versions_set
        filters['version_id'] = None
    return filters


def _list_memory(
    self: PostgresDocumentTableRepository,
    company: str,
    filters: dict[str, Any],
    limit: object,
) -> list[DocumentTable]:
    store = self._memory.get(company, {})
    rows = [r for r in store.values() if _matches(r, filters)]
    if filters['version_ids'] and not filters['version_id']:
        rows = [r for r in rows if str(r.version_id) in {str(x) for x in filters['version_ids']}]
    if limit is not None:
        rows = rows[: int(str(limit))]
    return rows


def _add_list_where(sql: str, params: dict[str, Any], filters: dict[str, Any]) -> str:
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
    return sql


async def _list_sql(
    self: PostgresDocumentTableRepository,
    company: str,
    filters: dict[str, Any],
    limit: object,
) -> list[DocumentTable]:
    params: dict[str, Any] = {'company_id': company}
    sql = f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id'
    sql = _add_list_where(sql, params, filters)
    sql += ' ORDER BY created_at ASC, id ASC'
    if limit is not None:
        sql += ' LIMIT :limit'
        params['limit'] = int(str(limit))
    result = await self._execute(sql, params)
    return [r for r in (_row_to_table(x) for x in await self._fetchall(result)) if r is not None]


async def _list(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> builtins.list[DocumentTable]:
    company = _company(company_id)
    if company_id is None and kwargs.get('company_id') is not None:
        company = _company(kwargs.pop('company_id'))
    elif company_id is None and kwargs.get('company') is not None:
        company = _company(kwargs.pop('company'))
    scalar_values, kwargs = _merge_list_args(args, kwargs)
    raw = _pop_list_filters(kwargs)
    _consume_scalar_args(scalar_values, raw)
    filters = _finalise_list_filters(raw)
    if self._session is None:
        return _list_memory(self, company, filters, raw['limit'])
    await self._set_rls_context(company)
    return await _list_sql(self, company, filters, raw['limit'])
