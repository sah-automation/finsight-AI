"""Auto-extracted helper for JobRepository.update_job."""

from __future__ import annotations

import contextlib
from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from .job_repository import (
    _TABLE,
    _as_str_or_none,
    _JobRecord,
    _normalise_status,
    _row_to_record,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, JobStatus

_MEMORY_UPDATE_FIELDS = (
    'progress',
    'error',
    'error_message',
    'message',
    'failure_reason',
    'receive_count',
    'document_id',
    'document_version_id',
    'version',
)


def _apply_memory_updates(
    data: dict[str, Any],
    status: JobStatus | str | None,
    kwargs: dict[str, object],
) -> _JobRecord:
    provided_status: Any = status
    if provided_status is None and 'status' in kwargs:
        provided_status = kwargs.get('status')
    new_status = _normalise_status(provided_status)
    if new_status is not None:
        data['status'] = new_status
    for field in _MEMORY_UPDATE_FIELDS:
        if field in kwargs and kwargs.get(field) is not None:
            data[field] = kwargs.get(field)
    if 'document_id' not in kwargs and kwargs.get('doc_id') is not None:
        data['document_id'] = kwargs.get('doc_id')
    for key, value in list(kwargs.items()):
        if key not in {'company_id', 'job_id', 'status'}:
            data.setdefault(key, value)
    return _JobRecord(data)


def _update_job_memory(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    status: JobStatus | str | None,
    kwargs: dict[str, object],
) -> object:
    store = self._memory.get(str(company_id), {})
    key = _as_str_or_none(job_id)
    existing = store.get(str(key)) if key is not None else None
    if existing is None:
        return None
    record = _apply_memory_updates(dict(existing), status, kwargs)
    if record.get('job_id') is None:
        record['job_id'] = key
    store[str(key)] = record
    return record


def _add_status_assignment(
    values: dict[str, Any],
    assignments: list[str],
    status_value: str | None,
) -> None:
    if status_value is None:
        return
    values['status_val'] = status_value
    assignments.append('status = :status_val')
    low = status_value.lower()
    if low == 'processing':
        assignments.append('started_at = COALESCE(started_at, now())')
    if low in {'committed', 'completed', 'done', 'failed'}:
        assignments.append('completed_at = COALESCE(completed_at, now())')


def _add_progress_assignment(
    values: dict[str, Any],
    assignments: list[str],
    kwargs: dict[str, object],
) -> None:
    if 'progress' not in kwargs:
        return
    val = kwargs.pop('progress')
    if val is not None:
        with contextlib.suppress(TypeError, ValueError):
            val = int(str(val))
        values['progress_val'] = val
        assignments.append('progress = :progress_val')


def _add_error_assignment(
    values: dict[str, Any],
    assignments: list[str],
    kwargs: dict[str, object],
) -> None:
    if not any(key in kwargs for key in ('error', 'error_message', 'message', 'failure_reason')):
        return
    val = kwargs.pop('error', None)
    if val is None:
        val = kwargs.pop('error_message', None)
    if val is None:
        val = kwargs.pop('message', None)
    if val is None:
        val = kwargs.pop('failure_reason', None)
    values['error_val'] = val
    assignments.append('error = :error_val')


def _add_receive_count_assignment(
    values: dict[str, Any],
    assignments: list[str],
    kwargs: dict[str, object],
) -> None:
    if 'receive_count' not in kwargs:
        return
    val = kwargs.pop('receive_count')
    if val is not None:
        with contextlib.suppress(TypeError, ValueError):
            val = int(str(val))
    values['receive_count_val'] = val if val is not None else None
    assignments.append('receive_count = COALESCE(:receive_count_val, receive_count)')


def _add_document_id_assignment(
    values: dict[str, Any],
    assignments: list[str],
    kwargs: dict[str, object],
) -> None:
    if not any(key in kwargs for key in ('document_id', 'documentId', 'doc_id')):
        return
    val = kwargs.pop('document_id', kwargs.pop('documentId', kwargs.pop('doc_id', None)))
    values['document_id_val'] = _as_str_or_none(val)
    assignments.append('document_id = COALESCE(:document_id_val, document_id)')


def _add_document_version_assignment(
    values: dict[str, Any],
    assignments: list[str],
    kwargs: dict[str, object],
) -> None:
    keys = ('document_version_id', 'documentVersionId', 'version_id', 'versionId', 'version')
    if not any(key in kwargs for key in keys):
        return
    val = kwargs.pop(
        'document_version_id',
        kwargs.pop(
            'documentVersionId',
            kwargs.pop('version_id', kwargs.pop('versionId', kwargs.pop('version', None))),
        ),
    )
    values['document_version_id_val'] = _as_str_or_none(val)
    assignments.append(
        'document_version_id = COALESCE(:document_version_id_val, document_version_id)'
    )


def _add_timestamp_assignments(
    values: dict[str, Any],
    assignments: list[str],
    kwargs: dict[str, object],
) -> None:
    if 'started_at' in kwargs:
        values['started_at_val'] = kwargs.pop('started_at')
        assignments.append('started_at = COALESCE(:started_at_val, started_at)')
    if 'completed_at' in kwargs:
        values['completed_at_val'] = kwargs.pop('completed_at')
        assignments.append('completed_at = COALESCE(:completed_at_val, completed_at)')


def _drop_unknown_update_kwargs(kwargs: dict[str, object]) -> None:
    for key in list(kwargs.keys()):
        if key in {'company_id', 'job_id'}:
            continue
        kwargs.pop(key, None)


def _build_update_values(
    status: JobStatus | str | None,
    kwargs: dict[str, object],
) -> tuple[dict[str, Any], list[str]]:
    provided_status: Any = status
    if provided_status is None and 'status' in kwargs:
        provided_status = kwargs.pop('status')
    kwargs.pop('status', None)
    values: dict[str, Any] = {}
    assignments: list[str] = []
    _add_status_assignment(values, assignments, _normalise_status(provided_status))
    _add_progress_assignment(values, assignments, kwargs)
    _add_error_assignment(values, assignments, kwargs)
    _add_receive_count_assignment(values, assignments, kwargs)
    _add_document_id_assignment(values, assignments, kwargs)
    _add_document_version_assignment(values, assignments, kwargs)
    _add_timestamp_assignments(values, assignments, kwargs)
    _drop_unknown_update_kwargs(kwargs)
    if not assignments:
        assignments.append('updated_at = updated_at')
    assignments.append('updated_at = now()')
    return values, assignments


async def _update_job_sql(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    values: dict[str, Any],
    assignments: list[str],
) -> object:
    params: dict[str, Any] = {
        'company_id': str(company_id),
        'job_id': _as_str_or_none(job_id),
    }
    params.update(values)
    sql = (
        f'UPDATE {_TABLE} SET {", ".join(assignments)} '
        'WHERE company_id = :company_id AND job_id = :job_id RETURNING *'
    )
    result = await self._execute(sql, params)
    row = await self._fetchone(result)
    return _row_to_record(row)


async def _update_job(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    *,
    status: JobStatus | str | None = None,
    **kwargs: object,
) -> object:
    if self._session is None:
        return _update_job_memory(self, company_id, job_id, status, kwargs)
    await self._set_rls_context(company_id)
    values, assignments = _build_update_values(status, kwargs)
    return await _update_job_sql(self, company_id, job_id, values, assignments)
