"""Auto-extracted helper for JobRepository.delete_job."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from .job_repository import (
    _TABLE,
    _as_str_or_none,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


async def _delete_job(
    self: Any,
    company_id: CompanyId,
    job_id: object,
    **kwargs: object,
) -> bool:
    if self._session is None:
        store = self._memory.get(str(company_id), {})
        key = _as_str_or_none(job_id)
        if key is not None and key in store:
            del store[key]
            return True
        return False
    await self._set_rls_context(company_id)
    params: dict[str, Any] = {
        'company_id': str(company_id),
        'job_id': _as_str_or_none(job_id),
    }
    sql = (
        f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND job_id = :job_id RETURNING job_id'
    )
    result = await self._execute(sql, params)
    row = await self._fetchone(result)
    if row is not None:
        return True
    rowcount = getattr(result, 'rowcount', None)
    if rowcount is not None:
        return bool(rowcount)
    return True
