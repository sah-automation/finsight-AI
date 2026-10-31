"""Auto-extracted helper for PostgresDocumentTableRepository._get."""

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
    _row_to_table,
)

if TYPE_CHECKING:
    from finsight.domain.entities.document_table import DocumentTable


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


def _parse_get_args(
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> tuple[object, object, object, object, object]:
    target = args[0] if args else None
    table_id = kwargs.pop('table_id', kwargs.pop('table', kwargs.pop('tableId', None)))
    row_id = kwargs.pop('id', kwargs.pop('document_table_id', kwargs.pop('row_id', None)))
    version_id = kwargs.pop('version_id', kwargs.pop('version', None))
    page = kwargs.pop('page', kwargs.pop('page_number', None))
    if target is None:
        target = kwargs.pop('target', None)
    if table_id is None and isinstance(target, str):
        row_id = row_id or target
    return target, table_id, row_id, version_id, page


def _matches_get_filters(
    row: DocumentTable,
    table_id: object,
    version_id: object,
    page: object,
) -> bool:
    if table_id is not None and str(row.table_id) != str(table_id):
        return False
    if version_id is not None and str(row.version_id) != str(version_id):
        return False
    if page is not None:
        return str(row.page if row.page is not None else row.page_number) == str(page)
    return True


def _get_memory(
    self: PostgresDocumentTableRepository,
    company: str,
    target: object,
    table_id: object,
    row_id: object,
    version_id: object,
    page: object,
) -> DocumentTable | None:
    store = self._memory.get(company, {})
    for rid in (row_id, target):
        if rid is not None and str(rid) in store:
            row = store[str(rid)]
            if _matches_get_filters(row, table_id, version_id, page):
                return row
    if table_id is not None:
        for row in store.values():
            if str(row.table_id) == str(table_id) and _matches_get_filters(
                row, table_id, version_id, page
            ):
                return row
    return None


async def _get_candidate(
    self: PostgresDocumentTableRepository,
    company: str,
    candidate_id: object,
    table_id: object,
    version_id: object,
) -> DocumentTable | None:
    result = await self._execute(
        f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id AND id = :id',
        {'company_id': company, 'id': str(candidate_id)},
    )
    candidate = _row_to_table(await self._fetchone(result))
    if candidate is None:
        return None
    if table_id is not None and str(candidate.table_id) != str(table_id):
        return None
    if version_id is not None and str(candidate.version_id) != str(version_id):
        return None
    return candidate


async def _get_by_table(
    self: PostgresDocumentTableRepository,
    company: str,
    table_id: object,
    version_id: object,
    page: object,
) -> DocumentTable | None:
    sql = (
        f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id AND table_id = :table_id'
    )
    params: dict[str, Any] = {'company_id': company, 'table_id': str(table_id)}
    if version_id is not None:
        sql += ' AND version_id = :version_id'
        params['version_id'] = str(version_id)
    if page is not None:
        sql += ' AND page_number = :page_number'
        params['page_number'] = page
    result = await self._execute(sql + ' LIMIT 1', params)
    return _row_to_table(await self._fetchone(result))


async def _get_sql(
    self: PostgresDocumentTableRepository,
    company: str,
    target: object,
    table_id: object,
    row_id: object,
    version_id: object,
    page: object,
) -> DocumentTable | None:
    await self._set_rls_context(company)
    candidate_id = row_id if row_id is not None else target
    if candidate_id is not None:
        candidate = await _get_candidate(self, company, candidate_id, table_id, version_id)
        if candidate is not None:
            return candidate
    if table_id is not None:
        by_table = await _get_by_table(self, company, table_id, version_id, page)
        if by_table is not None:
            return by_table
    rows = await self._list(company, version_id=version_id, page=page, table_id=table_id)
    return rows[0] if rows else None


async def _get(
    self: PostgresDocumentTableRepository, company_id: object, *args: object, **kwargs: object
) -> DocumentTable | None:
    company = _company(company_id if company_id is not None else kwargs.get('company_id'))
    target, table_id, row_id, version_id, page = _parse_get_args(args, kwargs)
    if self._session is None:
        row = _get_memory(self, company, target, table_id, row_id, version_id, page)
        if row is not None:
            return row
        rows = await self._list(company, version_id=version_id, page=page, table_id=table_id)
        return rows[0] if rows else None
    return await _get_sql(self, company, target, table_id, row_id, version_id, page)
