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


async def _update_job(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    *,
    status: JobStatus | str | None = None,
    **kwargs: object,
) -> object:
    if self._session is None:
        store = self._memory.get(str(company_id), {})
        key = _as_str_or_none(job_id)
        existing = store.get(str(key)) if key is not None else None
        if existing is None:
            return None
        data = dict(existing)
        provided_status: Any = status
        if provided_status is None and 'status' in kwargs:
            provided_status = kwargs.get('status')
        new_status = _normalise_status(provided_status)
        if new_status is not None:
            data['status'] = new_status
        for field in (
            'progress',
            'error',
            'error_message',
            'message',
            'failure_reason',
            'receive_count',
            'document_id',
            'document_version_id',
            'version',
        ):
            if field in kwargs and kwargs.get(field) is not None:
                data[field] = kwargs.get(field)
        if 'document_id' not in kwargs and kwargs.get('doc_id') is not None:
            data['document_id'] = kwargs.get('doc_id')
        for k, v in list(kwargs.items()):
            if k not in {'company_id', 'job_id', 'status'}:
                data.setdefault(k, v)
        record = _JobRecord(data)
        if 'job_id' not in record or record.get('job_id') is None:
            record['job_id'] = key
        store[str(key)] = record
        return record
    await self._set_rls_context(company_id)

    provided_status = status
    if provided_status is None and 'status' in kwargs:
        provided_status = kwargs.pop('status')
    kwargs.pop('status', None)

    values: dict[str, Any] = {}
    assignments: list[str] = []

    status_value = _normalise_status(provided_status)
    if status_value is not None:
        values['status_val'] = status_value
        assignments.append('status = :status_val')
        low = status_value.lower()
        if low == 'processing':
            assignments.append('started_at = COALESCE(started_at, now())')
        if low in {'committed', 'completed', 'done', 'failed'}:
            assignments.append('completed_at = COALESCE(completed_at, now())')

    # progress
    if 'progress' in kwargs:
        val = kwargs.pop('progress')
        if val is not None:
            with contextlib.suppress(TypeError, ValueError):
                val = int(str(val))
            values['progress_val'] = val
            assignments.append('progress = :progress_val')

    # error (allow explicit None)
    if (
        'error' in kwargs
        or 'error_message' in kwargs
        or 'message' in kwargs
        or 'failure_reason' in kwargs
    ):
        val = kwargs.pop('error', None)
        if val is None:
            val = kwargs.pop('error_message', None)
        if val is None:
            val = kwargs.pop('message', None)
        if val is None:
            val = kwargs.pop('failure_reason', None)
        values['error_val'] = val
        assignments.append('error = :error_val')

    # receive_count
    if 'receive_count' in kwargs:
        val = kwargs.pop('receive_count')
        if val is not None:
            with contextlib.suppress(TypeError, ValueError):
                val = int(str(val))
        values['receive_count_val'] = val if val is not None else None
        assignments.append('receive_count = COALESCE(:receive_count_val, receive_count)')

    # document ids
    if 'document_id' in kwargs or 'documentId' in kwargs or 'doc_id' in kwargs:
        val = kwargs.pop('document_id', kwargs.pop('documentId', kwargs.pop('doc_id', None)))
        values['document_id_val'] = _as_str_or_none(val)
        assignments.append('document_id = COALESCE(:document_id_val, document_id)')

    if (
        'document_version_id' in kwargs
        or 'documentVersionId' in kwargs
        or 'version_id' in kwargs
        or 'versionId' in kwargs
        or 'version' in kwargs
    ):
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

    # timestamps
    if 'started_at' in kwargs:
        val = kwargs.pop('started_at')
        values['started_at_val'] = val
        assignments.append('started_at = COALESCE(:started_at_val, started_at)')
    if 'completed_at' in kwargs:
        val = kwargs.pop('completed_at')
        values['completed_at_val'] = val
        assignments.append('completed_at = COALESCE(:completed_at_val, completed_at)')

    # passthrough unknown kwargs
    for key, _val in list(kwargs.items()):
        if key in {'company_id', 'job_id'}:
            continue
        kwargs.pop(key, None)

    if not assignments:
        assignments.append('updated_at = updated_at')

    assignments.append('updated_at = now()')

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
