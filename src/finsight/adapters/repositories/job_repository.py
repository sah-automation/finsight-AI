"""Postgres/Aurora job repository implementing the JobRepository port."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from finsight.core.types import CompanyId, JobStatus
from finsight.domain.ports.job_repository import JobRepository as JobRepositoryPort

from .base_repository import BaseRepository

_TABLE = 'jobs'


def _uuid_like(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


class _JobRecord(dict[str, Any]):
    """Flexible row wrapper supporting attribute access."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self.get(name)
        except Exception as exc:
            raise AttributeError(name) from exc


def _row_to_record(row: Any) -> _JobRecord | None:
    if row is None:
        return None
    mapping = getattr(row, '_mapping', None)
    data: dict[str, Any] = {}
    if mapping is not None:
        try:
            keys = list(mapping.keys())
        except Exception:
            keys = []
        for key in keys:
            try:
                data[str(key)] = mapping[key]
            except Exception:
                try:
                    data[str(key)] = mapping.get(key)
                except Exception:
                    pass
    if not data:
        try:
            data = {'value': row}
        except Exception:
            data = {}
    return _JobRecord(data)


def _pop(kwargs: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in kwargs:
            return kwargs.pop(name)
    return None


def _normalise_status(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'value'):
        try:
            return str(value.value)
        except Exception:
            pass
    return str(value)


class JobRepository(JobRepositoryPort, BaseRepository):
    """Concrete job repository with RLS context enforcement."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)

    async def create_job(
        self,
        company_id: CompanyId,
        job_id: object,
        *,
        status: JobStatus | str | None = None,
        **kwargs: object,
    ) -> object:
        await self._set_rls_context(company_id)

        status = status if status is not None else kwargs.pop('status', None)  # type: ignore[assignment]
        status_value = _normalise_status(status) or 'queued'
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

        conflict_target_present = 'job_id' in values

        columns = list(values.keys())
        placeholders = ', '.join(f':{c}' for c in columns)
        column_list = ', '.join(columns)

        if conflict_target_present:
            update_cols = [
                c for c in columns if c not in {'id', 'company_id', 'job_id', 'created_at'}
            ]
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
        record = _row_to_record(row)
        if record is None:
            return _JobRecord(dict(values))
        return record

    async def get_job(
        self,
        company_id: CompanyId,
        job_id: object,
        **kwargs: object,
    ) -> object:
        await self._set_rls_context(company_id)
        sql = f'SELECT * FROM {_TABLE} WHERE company_id = :company_id AND job_id = :job_id'
        params: dict[str, Any] = {
            'company_id': str(company_id),
            'job_id': _as_str_or_none(job_id),
        }
        status_filter = kwargs.pop('status', None)
        if status_filter is not None:
            sql += ' AND status = :status'
            params['status'] = _normalise_status(status_filter) or str(status_filter)
        document_id = kwargs.pop(
            'document_id', kwargs.pop('documentId', kwargs.pop('doc_id', None))
        )
        if document_id is not None:
            sql += ' AND document_id = :document_id'
            params['document_id'] = _as_str_or_none(document_id)
        result = await self._execute(sql, params)
        row = await self._fetchone(result)
        return _row_to_record(row)

    async def update_job(
        self,
        company_id: CompanyId,
        job_id: object,
        *,
        status: JobStatus | str | None = None,
        **kwargs: object,
    ) -> object:
        await self._set_rls_context(company_id)

        provided_status = status
        if provided_status is None and 'status' in kwargs:
            provided_status = kwargs.pop('status')  # type: ignore[assignment]
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
                try:
                    val = int(str(val))
                except (TypeError, ValueError):
                    pass
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
                try:
                    val = int(str(val))
                except (TypeError, ValueError):
                    pass
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
        for key, val in list(kwargs.items()):
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

    async def list_jobs(
        self,
        company_id: CompanyId,
        **kwargs: object,
    ) -> list[object]:
        await self._set_rls_context(company_id)
        where = ['company_id = :company_id']
        params: dict[str, Any] = {'company_id': str(company_id)}

        status_filter = kwargs.pop('status', None)
        if status_filter is None:
            status_filter = kwargs.pop('job_status', None)
        if status_filter is not None:
            where.append('status = :status')
            params['status'] = _normalise_status(status_filter) or str(status_filter)

        document_id = kwargs.pop(
            'document_id', kwargs.pop('documentId', kwargs.pop('doc_id', None))
        )
        if document_id is not None:
            where.append('document_id = :document_id')
            params['document_id'] = _as_str_or_none(document_id)

        document_version_id = kwargs.pop(
            'document_version_id',
            kwargs.pop(
                'documentVersionId', kwargs.pop('version_id', kwargs.pop('versionId', None))
            ),
        )
        if document_version_id is not None:
            where.append('document_version_id = :document_version_id')
            params['document_version_id'] = _as_str_or_none(document_version_id)

        job_id = kwargs.pop('job_id', kwargs.pop('jobId', kwargs.pop('id', None)))
        if job_id is not None:
            where.append('job_id = :job_id')
            params['job_id'] = _as_str_or_none(job_id)

        sql = f'SELECT * FROM {_TABLE} WHERE {" AND ".join(where)}'

        order_by = kwargs.pop('order_by', None) or kwargs.pop('orderBy', None) or 'created_at'
        direction = kwargs.pop('direction', None) or kwargs.pop('order', None) or 'DESC'
        if str(direction).upper() not in {'ASC', 'DESC'}:
            direction = 'DESC'
        if not order_by or not str(order_by).replace('_', '').isalnum():
            order_by = 'created_at'
        sql += f' ORDER BY {order_by} {direction}'

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

        result = await self._execute(sql, params)
        rows = await self._fetchall(result)
        records: list[object] = []
        for row in rows or []:
            record = _row_to_record(row)
            if record is not None:
                records.append(record)
        return records

    async def delete_job(
        self,
        company_id: CompanyId,
        job_id: object,
        **kwargs: object,
    ) -> bool:
        await self._set_rls_context(company_id)
        params: dict[str, Any] = {
            'company_id': str(company_id),
            'job_id': _as_str_or_none(job_id),
        }
        sql = f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND job_id = :job_id RETURNING job_id'
        result = await self._execute(sql, params)
        row = await self._fetchone(result)
        if row is not None:
            return True
        rowcount = getattr(result, 'rowcount', None)
        if rowcount is not None:
            return bool(rowcount)
        return True


PostgresJobRepository = JobRepository
AuroraJobRepository = JobRepository
PostgresJobRepo = JobRepository
AuroraJobRepo = JobRepository
JobRepositoryAdapter = JobRepository
RLSJobRepository = JobRepository
JobRepo = JobRepository
__all__ = [
    'AuroraJobRepo',
    'AuroraJobRepository',
    'JobRepo',
    'JobRepository',
    'JobRepositoryAdapter',
    'PostgresJobRepo',
    'PostgresJobRepository',
    'RLSJobRepository',
]
