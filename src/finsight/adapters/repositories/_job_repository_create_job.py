"""Auto-extracted helper for JobRepository.create_job."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
    _pop,
    _row_to_record,
    _uuid_like,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, JobStatus


async def _create_job(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    *,
    status: JobStatus | str | None = None,
    **kwargs: object,
) -> object:
    if self._session is not None:
        await self._set_rls_context(company_id)

    raw_status: Any = status if status is not None else kwargs.pop('status', None)
    status_value = _normalise_status(raw_status) or 'queued'
    progress = kwargs.pop('progress', 0)
    try:
        progress = int(str(progress)) if progress is not None else 0
    except (TypeError, ValueError):
        progress = 0

    error = kwargs.pop('error', None)
    if error is None:
        error = kwargs.pop('error_message', None) or kwargs.pop('message', None)
    if error is None:
        error = kwargs.pop('failure_reason', None)

    receive_count = kwargs.pop('receive_count', None)
    try:
        receive_count = 0 if receive_count is None else int(str(receive_count))
    except (TypeError, ValueError):
        receive_count = 0

    document_id = _pop(kwargs, 'document_id', 'documentId', 'doc_id', 'docId')
    document_version_id = _pop(
        kwargs, 'document_version_id', 'documentVersionId', 'version_id', 'versionId', 'version'
    )
    id_value = _pop(kwargs, 'id', 'job_pk', 'pk')

    started_at = _pop(kwargs, 'started_at', 'startedAt', 'started')
    completed_at = _pop(kwargs, 'completed_at', 'completedAt', 'completed')

    if status_value.lower() == 'processing' and started_at is None:
        started_at = datetime.now(UTC)
    if (
        status_value.lower() in {'committed', 'completed', 'done', 'failed'}
        and completed_at is None
    ):
        completed_at = datetime.now(UTC)

    job_id_str = _as_str_or_none(job_id)

    values: dict[str, Any] = {
        'company_id': str(company_id),
        'status': status_value,
        'progress': progress,
        'error': error,
        'receive_count': receive_count,
    }
    if job_id_str is not None:
        values['job_id'] = job_id_str
    if document_id is not None:
        values['document_id'] = _as_str_or_none(document_id)
    if document_version_id is not None:
        values['document_version_id'] = _as_str_or_none(document_version_id)
    if _as_str_or_none(id_value) is not None:
        values['id'] = _as_str_or_none(id_value)
    elif job_id_str is not None and _uuid_like(job_id_str):
        values['id'] = job_id_str
    if started_at is not None:
        values['started_at'] = started_at
    if completed_at is not None:
        values['completed_at'] = completed_at

    for key, val in list(kwargs.items()):
        if key in values:
            continue
        if key in {
            'company_id',
            'job_id',
            'status',
            'progress',
            'error',
            'receive_count',
            'document_id',
            'document_version_id',
            'id',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at',
        }:
            kwargs.pop(key, None)
            continue
        if key in {'error_text', 'receiveCount'}:
            values['error' if key == 'error_text' else 'receive_count'] = val
            kwargs.pop(key, None)

    if self._session is None:
        store = self._memory.setdefault(str(company_id), {})
        key: Any = values.get('job_id')  # type: ignore[no-redef]
        if key is None:
            key = _as_str_or_none(job_id)
        if key is None:
            key = str(uuid.uuid4())
        values.setdefault('job_id', key)
        record = _JobRecord(dict(values))
        store[str(key)] = record
        return record

    conflict_target_present = 'job_id' in values

    columns = list(values.keys())
    placeholders = ', '.join(f':{c}' for c in columns)
    column_list = ', '.join(columns)

    if conflict_target_present:
        update_cols = [c for c in columns if c not in {'id', 'company_id', 'job_id', 'created_at'}]
        sql = (
            f'INSERT INTO {_TABLE} ({column_list}) '
            f'VALUES ({placeholders}) '
            'ON CONFLICT (company_id, job_id) DO UPDATE SET '
            + ', '.join(f'{c} = EXCLUDED.{c}' for c in update_cols)
            + ', updated_at = now() '
            'RETURNING *'
        )
    else:
        sql = f'INSERT INTO {_TABLE} ({column_list}) VALUES ({placeholders}) RETURNING *'

    result = await self._execute(sql, values)
    row = await self._fetchone(result)
    record: _JobRecord | None = _row_to_record(row)  # type: ignore[no-redef]
    if record is None:
        return _JobRecord(dict(values))
    return record
