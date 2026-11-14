"""Shared base for tenant-aware vector-store adapters."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from sqlalchemy import text

_LOGGER = logging.getLogger(__name__)


class BaseVectorStore:
    """Common helpers for vector adapters that set RLS context per transaction."""

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

    @property
    def session(self) -> Any:
        return self._session

    async def _execute(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        session = self._session
        if session is None:
            raise RuntimeError('No database session configured')
        try:
            result = session.execute(text(sql), params or {})
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            if hasattr(session, 'rollback'):
                try:
                    rollback = session.rollback()
                    if inspect.isawaitable(rollback):
                        await rollback
                except Exception as exc:
                    _LOGGER.warning('vector store rollback failed: %s', exc)
            raise
        return result

    async def _fetchall(self, result: Any) -> Any:
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
        return value or []

    async def _set_rls_context(self, company_id: Any) -> None:
        await self._execute(
            "SELECT set_config('app.company_id', :company_id, true)",
            {'company_id': str(company_id)},
        )

    async def set_rls_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)

    async def set_company_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)

    async def set_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)

    async def ensure_rls_context(self, company_id: Any) -> None:
        await self._set_rls_context(company_id)


__all__ = ['BaseVectorStore']
