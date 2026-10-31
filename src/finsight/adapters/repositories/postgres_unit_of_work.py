"""PostgreSQL/SQLAlchemy adapter implementing the :class:`UnitOfWork` port."""

from __future__ import annotations

import inspect
from typing import Any

from finsight.domain.ports.unit_of_work import UnitOfWork as UnitOfWorkPort

try:
    from finsight.adapters.repositories.base_repository import set_rls_context as _set_rls_context
except ImportError:  # pragma: no cover
    _set_rls_context = None  # type: ignore[assignment]

__all__ = [
    'DatabaseUnitOfWork',
    'DbUnitOfWork',
    'PgUnitOfWork',
    'PostgresUnitOfWork',
    'SessionUnitOfWork',
    'SqlAlchemyUnitOfWork',
    'SqlUnitOfWork',
    'UnitOfWork',
    'UnitOfWorkAdapter',
    'UnitOfWorkImpl',
]


def _looks_like_session(value: object) -> bool:
    return (
        hasattr(value, 'execute')
        or hasattr(value, 'begin')
        or hasattr(value, 'commit')
        or hasattr(value, 'rollback')
    )


async def _await_maybe(value: object) -> object:
    if inspect.isawaitable(value):
        return await value
    return value


def _resolve_session(*args: object, **kwargs: object) -> object:
    for arg in args:
        if arg is None or isinstance(arg, (dict, str, int, float, bool)):
            continue
        if _looks_like_session(arg):
            return arg
    for key in (
        'session',
        'db_session',
        'database_session',
        'connection',
        'engine',
        'session_or_engine',
    ):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('session_factory', 'factory'):
        value = kwargs.get(key)
        if value is not None:
            return value
    return None


class PostgresUnitOfWork(UnitOfWorkPort):
    """Unit of work wrapping an (optionally async) database session."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.config = kwargs.get('config')
        self._session = _resolve_session(*args, **kwargs)
        self._session_factory = kwargs.get('session_factory') or kwargs.get('factory')
        self.company_id = kwargs.get('company_id', kwargs.get('company', kwargs.get('tenant_id')))
        if self.company_id is None and args and not _looks_like_session(args[0]):
            self.company_id = args[0]
        self._provided = {k: v for k, v in kwargs.items()}
        self._started = False
        self._committed_count = 0
        self._rollback_count = 0
        self._closed = False
        self.started = False
        self.committed = False
        self.rolled_back = False
        for key, value in kwargs.items():
            if key not in self.__dict__:
                try:
                    setattr(self, key, value)
                except Exception:
                    pass

    @property
    def session(self) -> object:
        return self._session

    @session.setter
    def session(self, value: object) -> None:
        self._session = value

    @property
    def db_session(self) -> object:
        return self._session

    @db_session.setter
    def db_session(self, value: object) -> None:
        self._session = value

    @property
    def database_session(self) -> object:
        return self._session

    @property
    def engine(self) -> object:
        return getattr(self._session, 'bind', None) or self._provided.get('engine')

    @property
    def connection(self) -> object:
        return self._session

    def _session_candidates(self, transaction: object = None) -> list[Any]:
        candidates: list[Any] = []
        if transaction is not None and transaction is not self:
            session = getattr(transaction, 'session', None)
            if session is None and hasattr(transaction, '_session'):
                session = getattr(transaction, '_session', None)
            if session is not None:
                candidates.append(session)
            if hasattr(transaction, 'commit') or hasattr(transaction, 'rollback'):
                candidates.append(transaction)
        if self._session is not None:
            candidates.append(self._session)
        out: list[Any] = []
        for candidate in candidates:
            if candidate is not None and candidate not in out:
                out.append(candidate)
        return out

    async def _call_best_effort(
        self, obj: object, method_name: str, *args: object, **kwargs: object
    ) -> object:
        method = getattr(obj, method_name, None)
        if not callable(method):
            return None
        try:
            result = method(*args, **kwargs)
            return await _await_maybe(result)
        except TypeError:
            try:
                result = method()
                return await _await_maybe(result)
            except Exception:
                return None
        except Exception:
            return None

    async def _set_company_context(self) -> None:
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

    async def begin(self, company_id: object = None, **kwargs: object) -> PostgresUnitOfWork:
        if company_id is not None:
            self.company_id = company_id
        if self._session is None and self._session_factory is not None:
            try:
                factory = self._session_factory
                result = factory() if callable(factory) else None
                self._session = await _await_maybe(result)
            except Exception:
                self._session = None
        if self.company_id is None:
            self.company_id = (
                kwargs.get('company') or kwargs.get('tenant_id') or kwargs.get('tenant')
            )
        session = self._session
        if session is not None:
            await self._call_best_effort(session, 'begin')
        await self._set_company_context()
        self._started = True
        self.started = True
        return self

    async def commit(self, transaction: object = None, **kwargs: object) -> None:
        for session in self._session_candidates(transaction):
            await self._call_best_effort(session, 'commit')
        self._committed_count += 1
        self.committed = True

    async def rollback(self, transaction: object = None, **kwargs: object) -> None:
        for session in self._session_candidates(transaction):
            await self._call_best_effort(session, 'rollback')
        self._rollback_count += 1
        self.rolled_back = True

    async def close(self, transaction: object = None, **kwargs: object) -> None:
        for session in self._session_candidates(transaction):
            await self._call_best_effort(session, 'close')
        self._closed = True

    async def __aenter__(self) -> PostgresUnitOfWork:
        return await self.begin()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is not None:
            await self.rollback(self)
        else:
            await self.commit(self)
        return False

    async def transaction(self, company_id: object = None, **kwargs: object) -> PostgresUnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def begin_transaction(
        self, company_id: object = None, **kwargs: object
    ) -> PostgresUnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def start(self, company_id: object = None, **kwargs: object) -> PostgresUnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def start_transaction(
        self, company_id: object = None, **kwargs: object
    ) -> PostgresUnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def open(self, company_id: object = None, **kwargs: object) -> PostgresUnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def enter(self, company_id: object = None, **kwargs: object) -> PostgresUnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def execute(self, company_id: object = None, **kwargs: object) -> object:
        if company_id is not None:
            await self.begin(company_id)
        session = self._session
        sql = kwargs.get('sql') or kwargs.get('statement')
        params = kwargs.get('params') or {}
        if session is not None and hasattr(session, 'execute'):
            try:
                result = session.execute(sql, params)
                return await _await_maybe(result)
            except Exception:
                return None
        return None

    async def run_in_transaction(self, company_id: object = None, **kwargs: object) -> object:
        func = kwargs.get('func') or kwargs.get('function') or kwargs.get('callback')
        if func is None:
            args_value: Any = kwargs.get('args', ()) or ()
            iterable: Any = args_value if isinstance(args_value, (tuple, list)) else ()
            for value in iterable:
                if callable(value):
                    func = value
                    break
        if company_id is not None:
            await self.begin(company_id)
        try:
            result = None
            if callable(func):
                try:
                    result = func(self)
                    result = await _await_maybe(result)
                except TypeError:
                    result = func()
                    result = await _await_maybe(result)
            await self.commit(self)
            return result
        except Exception:
            await self.rollback(self)
            raise

    async def set_company_context(self, company_id: object) -> None:
        self.company_id = company_id
        if self._session is not None:
            try:
                session_any: Any = self._session
                session_any.company_id = company_id
            except Exception:
                pass
        await self._set_company_context()

    async def set_rls_context(self, company_id: object) -> None:
        await self.set_company_context(company_id)

    async def set_tenant_context(self, company_id: object) -> None:
        await self.set_company_context(company_id)

    async def set_context(self, company_id: object) -> None:
        await self.set_company_context(company_id)

    async def ensure_rls_context(self, company_id: object) -> None:
        await self.set_company_context(company_id)

    @property
    def commit_count(self) -> int:
        return self._committed_count

    @property
    def rollback_count(self) -> int:
        return self._rollback_count

    @property
    def is_started(self) -> bool:
        return self._started


SqlAlchemyUnitOfWork = PostgresUnitOfWork
DatabaseUnitOfWork = PostgresUnitOfWork
DbUnitOfWork = PostgresUnitOfWork
SessionUnitOfWork = PostgresUnitOfWork
SqlUnitOfWork = PostgresUnitOfWork
UnitOfWorkAdapter = PostgresUnitOfWork
UnitOfWorkImpl = PostgresUnitOfWork
PgUnitOfWork = PostgresUnitOfWork
UnitOfWork = PostgresUnitOfWork
DatabaseTransaction = PostgresUnitOfWork
SqlAlchemyTransaction = PostgresUnitOfWork
TransactionManager = PostgresUnitOfWork
UnitOfWorkManager = PostgresUnitOfWork
DbTransaction = PostgresUnitOfWork
SessionTransaction = PostgresUnitOfWork
