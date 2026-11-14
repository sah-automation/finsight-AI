"""Shared base for tenant-aware (RLS) repository adapters."""

from __future__ import annotations

import inspect
from typing import Any

from sqlalchemy import text


class BaseRepository:
    """Common helpers for repositories that set RLS context per transaction."""

    def __init__(
        self,
        session: Any | None = None,
        session_or_engine: Any | None = None,
        connection: Any | None = None,
        engine: Any | None = None,
        db_session: Any | None = None,
        **kwargs: Any,
    ) -> None:
        chosen = (
            session
            if session is not None
            else session_or_engine
            if session_or_engine is not None
            else connection
            if connection is not None
            else engine
            if engine is not None
            else db_session
            if db_session is not None
            else kwargs.get('session')
            or kwargs.get('session_or_engine')
            or kwargs.get('connection')
            or kwargs.get('engine')
        )
        self._session = chosen
        self._session_or_engine = chosen
        self._rls_company_id: Any = None

    @property
    def session(self) -> Any:
        return self._session

    async def _raw_execute(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        session = self._session
        if session is None:
            raise RuntimeError('No database session configured')
        result = session.execute(text(sql), params or {})
        if inspect.isawaitable(result):
            result = await result
        return result

    async def _execute(self, sql: str, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        session = self._session
        if session is None:
            raise RuntimeError('No database session configured')
        if kwargs.get('company_id') is not None:
            self._rls_company_id = kwargs.get('company_id')
        tenant = self._rls_company_id
        try:
            if tenant is not None:
                await self._raw_execute(
                    "SELECT set_config('app.company_id', :company_id, true)",
                    {'company_id': str(tenant)},
                )
            result = await self._raw_execute(sql, params or {})
            if hasattr(session, 'commit') and callable(getattr(session, 'commit', None)):
                commit_result = session.commit()
                if inspect.isawaitable(commit_result):
                    await commit_result
            return result
        except Exception:
            if hasattr(session, 'rollback') and callable(getattr(session, 'rollback', None)):
                try:
                    rollback_result = session.rollback()
                    if inspect.isawaitable(rollback_result):
                        await rollback_result
                except Exception:
                    pass
            self._rls_company_id = None
            raise

    async def _run(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        return await self._execute(sql, params)

    async def _fetchone(self, result: Any) -> Any:
        """Fetch one row, awaiting the result method when it is awaitable."""
        if result is None:
            return None
        fetch = getattr(result, 'fetchone', None)
        if fetch is None:
            return result
        value = fetch()
        if inspect.isawaitable(value):
            value = await value
        return value

    async def _fetchall(self, result: Any) -> Any:
        """Fetch all rows, awaiting the result method when it is awaitable."""
        if result is None:
            return []
        fetch = getattr(result, 'fetchall', None)
        if fetch is None:
            try:
                return list(result)
            except TypeError:
                return []
        value = fetch()
        if inspect.isawaitable(value):
            value = await value
        if value is None:
            return []
        return value

    async def _set_rls_context(self, company_id: Any) -> None:
        """Stage tenant context so the next ``_execute`` applies it within one tx."""
        self._rls_company_id = company_id
        session = self._session
        if session is not None:
            try:
                session_any: Any = session
                session_any.company_id = company_id
            except Exception:
                pass

    async def set_rls_context(self, company_id: Any) -> None:
        """Public alias for :meth:`_set_rls_context`."""
        await self._set_rls_context(company_id)

    @staticmethod
    async def set_tenant_context(session_or_engine: Any, company_id: Any) -> None:
        """Module-level helper to set RLS context on a given session/engine."""
        result = session_or_engine.execute(
            text("SELECT set_config('app.company_id', :company_id, true)"),
            {'company_id': str(company_id)},
        )
        if inspect.isawaitable(result):
            await result

    async def set_company_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)

    async def set_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)

    async def ensure_rls_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)

    async def set_tenant_rls_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)


# Module-level convenience (used by callers that do not instantiate a repository).
async def set_rls_context(session_or_engine: Any, company_id: Any) -> None:
    """Set RLS context on the provided session/engine."""
    await BaseRepository.set_tenant_context(session_or_engine, company_id)


async def set_company_context(session_or_engine: Any, company_id: Any) -> None:
    await set_rls_context(session_or_engine, company_id)


async def set_tenant_context(session_or_engine: Any, company_id: Any) -> None:
    await set_rls_context(session_or_engine, company_id)


async def set_app_company_id(session_or_engine: Any, company_id: Any) -> None:
    await set_rls_context(session_or_engine, company_id)


def build_set_rls_sql(company_id: Any) -> str:
    # Escape single quotes to avoid SQL injection when emitting a literal.
    value = str(company_id).replace(chr(39), chr(39) + chr(39))
    return f"SET LOCAL app.company_id = '{value}'"
