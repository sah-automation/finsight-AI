"""Compatibility alias module for the UnitOfWork adapter.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from __future__ import annotations

from .postgres_unit_of_work import (
    DatabaseTransaction,
    DatabaseUnitOfWork,
    DbTransaction,
    DbUnitOfWork,
    PgUnitOfWork,
    PostgresUnitOfWork,
    SessionTransaction,
    SessionUnitOfWork,
    SqlAlchemyTransaction,
    SqlAlchemyUnitOfWork,
    SqlUnitOfWork,
    TransactionManager,
    UnitOfWork,
    UnitOfWorkAdapter,
    UnitOfWorkImpl,
    UnitOfWorkManager,
)

__all__ = [
    'DatabaseTransaction',
    'DatabaseUnitOfWork',
    'DbTransaction',
    'DbUnitOfWork',
    'PgUnitOfWork',
    'PostgresUnitOfWork',
    'SessionTransaction',
    'SessionUnitOfWork',
    'SqlAlchemyTransaction',
    'SqlAlchemyUnitOfWork',
    'SqlUnitOfWork',
    'TransactionManager',
    'UnitOfWork',
    'UnitOfWorkAdapter',
    'UnitOfWorkImpl',
    'UnitOfWorkManager',
]
