"""Auto-extracted helper for JobRepository.get_job."""

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


async def _get_job(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    **kwargs: object,
) -> object:
    if self._session is None:
        store = self._memory.get(str(company_id), {})
        key = _as_str_or_none(job_id)
        record = store.get(str(key)) if key is not None and str(key) in store else None
        if record is not None:
            status_filter = kwargs.get('status', kwargs.get('job_status'))
            if status_filter is not None and _normalise_status(status_filter) != record.get(
                'status'
            ):
                return None
        return record
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
    document_id = kwargs.pop('document_id', kwargs.pop('documentId', kwargs.pop('doc_id', None)))
    if document_id is not None:
        sql += ' AND document_id = :document_id'
        params['document_id'] = _as_str_or_none(document_id)
    result = await self._execute(sql, params)
    row = await self._fetchone(result)
    return _row_to_record(row)
