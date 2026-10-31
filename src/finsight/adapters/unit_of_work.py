"""Compatibility alias module for the UnitOfWork adapter."""

from __future__ import annotations

from finsight.adapters.repositories.postgres_unit_of_work import (
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
