"""Auto-extracted helper for JobRepository.list_jobs."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from .job_repository import (
    _TABLE,
    _as_str_or_none,
    _normalise_status,
    _row_to_record,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


def _filter_memory_jobs(records: list[Any], kwargs: dict[str, object]) -> list[Any]:
    status_filter = kwargs.get('status', kwargs.get('job_status'))
    if status_filter is not None:
        normalised = _normalise_status(status_filter)
        records = [
            r
            for r in records
            if r.get('status') == normalised or r.get('status') == str(status_filter)
        ]
    document_id = kwargs.get('document_id', kwargs.get('documentId', kwargs.get('doc_id')))
    if document_id is not None:
        records = [
            r
            for r in records
            if r.get('document_id') == document_id or str(r.get('document_id')) == str(document_id)
        ]
    job_id = kwargs.get('job_id', kwargs.get('jobId', kwargs.get('id')))
    if job_id is not None:
        records = [
            r for r in records if r.get('job_id') == job_id or str(r.get('job_id')) == str(job_id)
        ]
    return records


def _list_jobs_memory(self: Any, company_id: CompanyId, kwargs: dict[str, object]) -> list[Any]:
    store = self._memory.get(str(company_id), {})
    return _filter_memory_jobs(list(store.values()), kwargs)


def _add_job_filter_where(
    where: list[str],
    params: dict[str, Any],
    kwargs: dict[str, object],
) -> None:
    status_filter = kwargs.pop('status', None)
    if status_filter is None:
        status_filter = kwargs.pop('job_status', None)
    if status_filter is not None:
        where.append('status = :status')
        params['status'] = _normalise_status(status_filter) or str(status_filter)
    document_id = kwargs.pop('document_id', kwargs.pop('documentId', kwargs.pop('doc_id', None)))
    if document_id is not None:
        where.append('document_id = :document_id')
        params['document_id'] = _as_str_or_none(document_id)
    document_version_id = kwargs.pop(
        'document_version_id',
        kwargs.pop('documentVersionId', kwargs.pop('version_id', kwargs.pop('versionId', None))),
    )
    if document_version_id is not None:
        where.append('document_version_id = :document_version_id')
        params['document_version_id'] = _as_str_or_none(document_version_id)
    job_id = kwargs.pop('job_id', kwargs.pop('jobId', kwargs.pop('id', None)))
    if job_id is not None:
        where.append('job_id = :job_id')
        params['job_id'] = _as_str_or_none(job_id)


def _append_job_order(sql: str, kwargs: dict[str, object]) -> str:
    order_by = kwargs.pop('order_by', None) or kwargs.pop('orderBy', None) or 'created_at'
    direction = kwargs.pop('direction', None) or kwargs.pop('order', None) or 'DESC'
    if str(direction).upper() not in {'ASC', 'DESC'}:
        direction = 'DESC'
    if not order_by or not str(order_by).replace('_', '').isalnum():
        order_by = 'created_at'
    return f'{sql} ORDER BY {order_by} {direction}'


def _append_job_pagination(
    sql: str,
    params: dict[str, Any],
    kwargs: dict[str, object],
) -> str:
    limit = kwargs.pop('limit', None)
    if limit is None:
        limit = kwargs.pop('page_size', None)
    if limit is not None:
        try:
            params['limit'] = int(str(limit))
            sql += ' LIMIT :limit'
        except (TypeError, ValueError):
            pass
    offset = kwargs.pop('offset', None)
    if offset is None:
        offset = kwargs.pop('skip', None)
    if offset is not None:
        try:
            params['offset'] = int(str(offset))
            sql += ' OFFSET :offset'
        except (TypeError, ValueError):
            pass
    return sql


async def _list_jobs_sql(
    self: Any, company_id: CompanyId, kwargs: dict[str, object]
) -> list[object]:
    where = ['company_id = :company_id']
    params: dict[str, Any] = {'company_id': str(company_id)}
    _add_job_filter_where(where, params, kwargs)
    sql = f'SELECT * FROM {_TABLE} WHERE {" AND ".join(where)}'
    sql = _append_job_order(sql, kwargs)
    sql = _append_job_pagination(sql, params, kwargs)
    result = await self._execute(sql, params)
    rows = await self._fetchall(result)
    records: list[object] = []
    for row in rows or []:
        record = _row_to_record(row)
        if record is not None:
            records.append(record)
    return records


async def _list_jobs(
    self: Any,
    company_id: CompanyId,
    **kwargs: object,
) -> list[object]:
    if self._session is None:
        return _list_jobs_memory(self, company_id, kwargs)
    await self._set_rls_context(company_id)
    return await _list_jobs_sql(self, company_id, kwargs)
