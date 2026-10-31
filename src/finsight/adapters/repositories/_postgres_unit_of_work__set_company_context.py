"""Auto-extracted helper for PostgresUnitOfWork._set_company_context."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
try:
    from finsight.adapters.repositories.base_repository import (
        set_rls_context as _set_rls_context,
    )
except ImportError:  # pragma: no cover
    _set_rls_context = None  # type: ignore[assignment]

from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _set_company_context(self: PostgresUnitOfWork) -> None:
    company = self.company_id
    if company is None:
        return
    session = self._session
    if session is None:
        return
    try:
        session_any: Any = session
        session_any.company_id = company
    except Exception:
        pass
    try:
        if callable(_set_rls_context):
            await _set_rls_context(session, company)
            return
    except Exception:
        pass
    try:
        if hasattr(session, 'execute'):
            from sqlalchemy import text

            result = session.execute(
                text("SELECT set_config('app.company_id', :company_id, true)"),
                {'company_id': str(company)},
            )
            await _await_maybe(result)
    except Exception:
        pass
