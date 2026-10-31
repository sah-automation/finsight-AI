"""PostgreSQL/SQLAlchemy adapter implementing the :class:`UnitOfWork` port."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.unit_of_work import UnitOfWork as UnitOfWorkPort

from ._postgres_unit_of_work_shared import (
    _looks_like_session,
    _resolve_session,
)


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

    def _session_candidates(self, *args: Any, **kwargs: Any) -> list[Any]:
        from ._postgres_unit_of_work__session_candidates import (
            _session_candidates as _adapter_method,
        )

        return _adapter_method(self, *args, **kwargs)

    async def _call_best_effort(self, *args: Any, **kwargs: Any) -> object:
        from ._postgres_unit_of_work__call_best_effort import _call_best_effort as _adapter_method

        return await _adapter_method(self, *args, **kwargs)

    async def _set_company_context(self, *args: Any, **kwargs: Any) -> None:
        from ._postgres_unit_of_work__set_company_context import (
            _set_company_context as _adapter_method,
        )

        await _adapter_method(self, *args, **kwargs)

    async def begin(self, company_id: Any = None, *args: Any, **kwargs: Any) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_begin import _begin as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def commit(self, transaction: object = None, **kwargs: object) -> None:
        from ._postgres_unit_of_work_commit import _commit as _adapter_method

        await _adapter_method(self, transaction, **kwargs)

    async def rollback(self, transaction: object = None, **kwargs: object) -> None:
        from ._postgres_unit_of_work_rollback import _rollback as _adapter_method

        await _adapter_method(self, transaction, **kwargs)

    async def close(self, transaction: object = None, **kwargs: object) -> None:
        from ._postgres_unit_of_work_close import _close as _adapter_method

        await _adapter_method(self, transaction, **kwargs)

    async def __aenter__(self) -> PostgresUnitOfWork:
        return await self.begin()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is not None:
            await self.rollback(self)
        else:
            await self.commit(self)
        return False

    async def transaction(
        self, company_id: Any = None, *args: Any, **kwargs: Any
    ) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_transaction import _transaction as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def begin_transaction(self, company_id: Any = None, **kwargs: Any) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_begin_transaction import _begin_transaction as _adapter_method

        return await _adapter_method(self, company_id, **kwargs)

    async def start(self, company_id: Any = None, *args: Any, **kwargs: Any) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_start import _start as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def start_transaction(self, company_id: Any = None, **kwargs: Any) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_start_transaction import _start_transaction as _adapter_method

        return await _adapter_method(self, company_id, **kwargs)

    async def open(self, company_id: Any = None, *args: Any, **kwargs: Any) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_open import _open as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def enter(self, company_id: Any = None, *args: Any, **kwargs: Any) -> PostgresUnitOfWork:
        from ._postgres_unit_of_work_enter import _enter as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def execute(self, company_id: Any = None, *args: Any, **kwargs: Any) -> object:
        from ._postgres_unit_of_work_execute import _execute as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def run_in_transaction(self, company_id: Any = None, *args: Any, **kwargs: Any) -> object:
        from ._postgres_unit_of_work_run_in_transaction import (
            _run_in_transaction as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def set_company_context(self, company_id: Any = None, *args: Any, **kwargs: Any) -> None:
        from ._postgres_unit_of_work_set_company_context import (
            _set_company_context as _adapter_method,
        )

        await _adapter_method(self, company_id, *args, **kwargs)

    async def set_rls_context(self, company_id: Any = None, *args: Any, **kwargs: Any) -> None:
        from ._postgres_unit_of_work_set_rls_context import _set_rls_context as _adapter_method

        await _adapter_method(self, company_id, *args, **kwargs)

    async def set_tenant_context(self, company_id: Any = None, *args: Any, **kwargs: Any) -> None:
        from ._postgres_unit_of_work_set_tenant_context import (
            _set_tenant_context as _adapter_method,
        )

        await _adapter_method(self, company_id, *args, **kwargs)

    async def set_context(self, company_id: Any = None, *args: Any, **kwargs: Any) -> None:
        from ._postgres_unit_of_work_set_context import _set_context as _adapter_method

        await _adapter_method(self, company_id, *args, **kwargs)

    async def ensure_rls_context(self, company_id: Any = None, *args: Any, **kwargs: Any) -> None:
        from ._postgres_unit_of_work_ensure_rls_context import (
            _ensure_rls_context as _adapter_method,
        )

        await _adapter_method(self, company_id, *args, **kwargs)

    @property
    def commit_count(self) -> int:
        return self._committed_count

    @property
    def rollback_count(self) -> int:
        return self._rollback_count

    @property
    def is_started(self) -> bool:
        return self._started


# Compatibility aliases (preserved for external imports)
DatabaseTransaction = PostgresUnitOfWork
DatabaseUnitOfWork = PostgresUnitOfWork
DbTransaction = PostgresUnitOfWork
DbUnitOfWork = PostgresUnitOfWork
PgUnitOfWork = PostgresUnitOfWork
SessionTransaction = PostgresUnitOfWork
SessionUnitOfWork = PostgresUnitOfWork
SqlAlchemyTransaction = PostgresUnitOfWork
SqlAlchemyUnitOfWork = PostgresUnitOfWork
SqlUnitOfWork = PostgresUnitOfWork
TransactionManager = PostgresUnitOfWork
UnitOfWork = PostgresUnitOfWork
UnitOfWorkAdapter = PostgresUnitOfWork
UnitOfWorkImpl = PostgresUnitOfWork
UnitOfWorkManager = PostgresUnitOfWork
