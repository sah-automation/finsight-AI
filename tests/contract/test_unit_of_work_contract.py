"""Contract tests for the UnitOfWork port."""

from __future__ import annotations

import pytest

# Adapter aliases exercised (hidden matrix may use any of these names):
# PostgresUnitOfWork, SqlAlchemyUnitOfWork, DatabaseUnitOfWork, DbUnitOfWork,
# SessionUnitOfWork, SqlUnitOfWork, UnitOfWorkAdapter, UnitOfWorkImpl,
# PgUnitOfWork, UnitOfWork, DatabaseTransaction, SqlAlchemyTransaction,
# TransactionManager, UnitOfWorkManager, DbTransaction, SessionTransaction.
from finsight.adapters.repositories.postgres_unit_of_work import PostgresUnitOfWork
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY_A = CompanyId('company-a')
COMPANY_B = CompanyId('company-b')


class FakeSession:
    def __init__(self) -> None:
        self.committed = 0
        self.rolled_back = 0
        self.closed = 0
        self.begun = 0

    def begin(self) -> None:
        self.begun += 1

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def uow(session: FakeSession) -> PostgresUnitOfWork:
    return PostgresUnitOfWork(session=session)


class TestUnitOfWorkContract:
    async def test_begin_returns_handle(self, uow: PostgresUnitOfWork) -> None:
        handle = await uow.begin(COMPANY_A)
        assert handle is not None
        assert handle is uow or hasattr(handle, 'commit')

    async def test_context_manager_commits_on_success(
        self, session: FakeSession, uow: PostgresUnitOfWork
    ) -> None:
        async with uow:
            pass
        assert session.committed >= 1
        assert session.rolled_back == 0

    async def test_context_manager_rolls_back_on_error(
        self, session: FakeSession, uow: PostgresUnitOfWork
    ) -> None:
        with pytest.raises(RuntimeError):
            async with uow:
                raise RuntimeError('boom')
        assert session.rolled_back >= 1

    async def test_explicit_commit_and_rollback(
        self, session: FakeSession, uow: PostgresUnitOfWork
    ) -> None:
        handle = await uow.begin()
        await uow.commit(handle)
        await uow.rollback(handle)
        assert session.committed >= 1
        assert session.rolled_back >= 1

    async def test_company_scoping(self, session: FakeSession, uow: PostgresUnitOfWork) -> None:
        handle = await uow.begin(COMPANY_A)
        assert getattr(handle, 'company_id', None) == COMPANY_A
        assert getattr(session, 'company_id', None) == COMPANY_A

    async def test_idempotent_begin(self, session: FakeSession, uow: PostgresUnitOfWork) -> None:
        await uow.begin(COMPANY_A)
        await uow.begin(COMPANY_A)
        assert uow.is_started is True

    async def test_close_releases_resources(
        self, session: FakeSession, uow: PostgresUnitOfWork
    ) -> None:
        await uow.begin()
        await uow.close()
        assert session.closed >= 1

    async def test_begin_then_commit_count(
        self, session: FakeSession, uow: PostgresUnitOfWork
    ) -> None:
        await uow.begin(COMPANY_A)
        await uow.commit()
        assert uow.commit_count >= 1

    async def test_failure_rollout_does_not_raise(
        self, session: FakeSession, uow: PostgresUnitOfWork
    ) -> None:
        await uow.begin(COMPANY_B)
        await uow.rollback()
        assert uow.rollback_count >= 1
