"""Contract tests for the UserRepository port."""

from __future__ import annotations

import pytest

from finsight.adapters.repositories.user_repository import (
    PostgresUserRepository,
    UserRepository,
)
from finsight.core.types import CompanyId, Role, UserId

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
USER = UserId('user-1')
OTHER_USER = UserId('user-2')


@pytest.fixture
def repository() -> UserRepository:
    return UserRepository()


class TestUserRepositoryContract:
    async def test_create_and_get_roundtrip(self, repository: UserRepository) -> None:
        created = await repository.create_user(
            COMPANY, USER, 'alice@example.com', Role('system_admin')
        )

        assert created is not None
        assert created.id == USER
        assert created.company_id == COMPANY
        assert created.email == 'alice@example.com'

        found = await repository.get_user(COMPANY, USER)
        assert found is not None
        assert found.id == USER

    async def test_get_missing_returns_none(self, repository: UserRepository) -> None:
        assert await repository.get_user(COMPANY, USER) is None

    async def test_company_isolation(self, repository: UserRepository) -> None:
        await repository.create_user(COMPANY, USER, 'alice@example.com', Role('system_admin'))
        await repository.create_user(
            OTHER_COMPANY, OTHER_USER, 'bob@example.com', Role('executive_leadership')
        )

        assert await repository.get_user(COMPANY, USER) is not None
        assert await repository.get_user(OTHER_COMPANY, USER) is None
        assert await repository.get_user(OTHER_COMPANY, OTHER_USER) is not None

        users = await repository.list_users(COMPANY)
        assert len(users) == 1
        assert users[0].company_id == COMPANY

    async def test_get_by_email(self, repository: UserRepository) -> None:
        await repository.create_user(COMPANY, USER, 'alice@example.com', Role('system_admin'))

        found = await repository.get_user_by_email(COMPANY, 'alice@example.com')
        missing = await repository.get_user_by_email(COMPANY, 'missing@example.com')
        foreign = await repository.get_user_by_email(OTHER_COMPANY, 'alice@example.com')

        assert found is not None
        assert missing is None
        assert foreign is None

    async def test_update_preserves_unset_fields(self, repository: UserRepository) -> None:
        await repository.create_user(COMPANY, USER, 'alice@example.com', Role('system_admin'))

        updated = await repository.update_user(COMPANY, USER, role=Role('executive_leadership'))
        assert updated is not None
        assert updated.role == Role('executive_leadership')
        assert updated.email == 'alice@example.com'

        assert (
            await repository.update_user(OTHER_COMPANY, USER, role=Role('executive_leadership'))
            is None
        )

    async def test_delete_returns_false_for_missing(self, repository: UserRepository) -> None:
        await repository.create_user(COMPANY, USER, 'alice@example.com', Role('system_admin'))

        assert await repository.delete_user(COMPANY, USER) is True
        assert await repository.delete_user(COMPANY, USER) is False
        assert await repository.get_user(COMPANY, USER) is None

    async def test_create_is_idempotent(self, repository: UserRepository) -> None:
        await repository.create_user(COMPANY, USER, 'alice@example.com', Role('system_admin'))
        await repository.create_user(
            COMPANY, USER, 'alice@example.com', Role('executive_leadership')
        )

        users = await repository.list_users(COMPANY)
        assert len(users) == 1
        found = await repository.get_user(COMPANY, USER)
        assert found is not None
        assert found.role == Role('executive_leadership')


_PostgresUserRepository = PostgresUserRepository
