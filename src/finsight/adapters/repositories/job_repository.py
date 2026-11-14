"""Postgres/Aurora job repository implementing the JobRepository port."""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

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
                with contextlib.suppress(Exception):
                    data[str(key)] = mapping.get(key)
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
        self._memory: dict[str, dict[str, _JobRecord]] = {}

    async def create_job(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._job_repository_create_job import _create_job as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def get_job(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._job_repository_get_job import _get_job as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def update_job(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._job_repository_update_job import _update_job as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def list_jobs(self, company_id: Any, *args: Any, **kwargs: Any) -> list[object]:
        from ._job_repository_list_jobs import _list_jobs as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def delete_job(self, company_id: Any, *args: Any, **kwargs: Any) -> bool:
        from ._job_repository_delete_job import _delete_job as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)


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
