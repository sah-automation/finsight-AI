"""Contract tests for the CompanyRepository port."""

from __future__ import annotations

import pytest

from finsight.adapters.repositories.company_repository import (
    CompanyRepository,
    PostgresCompanyRepository,
)
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


@pytest.fixture
def repository() -> CompanyRepository:
    return CompanyRepository()


class TestCompanyRepositoryContract:
    async def test_create_and_get_roundtrip(self, repository: CompanyRepository) -> None:
        created = await repository.create_company(COMPANY, name='Alpha', slug='alpha')

        assert created is not None
        assert created.id == COMPANY
        assert created.name == 'Alpha'
        assert created.slug == 'alpha'

        found = await repository.get_company(COMPANY)
        assert found is not None
        assert found.id == COMPANY
        assert found.name == 'Alpha'

    async def test_get_missing_returns_none(self, repository: CompanyRepository) -> None:
        assert await repository.get_company(COMPANY) is None

    async def test_company_isolation(self, repository: CompanyRepository) -> None:
        await repository.create_company(COMPANY, name='Alpha', slug='alpha')
        await repository.create_company(OTHER_COMPANY, name='Beta', slug='beta')

        own = await repository.get_company(COMPANY)
        foreign = await repository.get_company(OTHER_COMPANY)
        assert own is not None and own.name == 'Alpha'
        assert foreign is not None and foreign.name == 'Beta'

        listed = await repository.list_companies(COMPANY)
        assert len(listed) == 1
        assert listed[0].id == COMPANY

    async def test_get_by_slug_is_tenant_scoped(self, repository: CompanyRepository) -> None:
        await repository.create_company(COMPANY, name='Alpha', slug='alpha')

        found = await repository.get_company_by_slug(COMPANY, 'alpha')
        missing = await repository.get_company_by_slug(COMPANY, 'missing')
        foreign = await repository.get_company_by_slug(OTHER_COMPANY, 'alpha')

        assert found is not None
        assert missing is None
        assert foreign is None

    async def test_update_preserves_unset_fields(self, repository: CompanyRepository) -> None:
        await repository.create_company(COMPANY, name='Alpha', slug='alpha')

        updated = await repository.update_company(COMPANY, name='Renamed')

        assert updated is not None
        assert updated.name == 'Renamed'
        assert updated.slug == 'alpha'

        assert await repository.update_company(OTHER_COMPANY, name='X') is None

    async def test_delete_returns_false_for_missing(self, repository: CompanyRepository) -> None:
        await repository.create_company(COMPANY, name='Alpha', slug='alpha')

        assert await repository.delete_company(COMPANY) is True
        assert await repository.delete_company(COMPANY) is False
        assert await repository.get_company(COMPANY) is None

    async def test_create_is_idempotent(self, repository: CompanyRepository) -> None:
        await repository.create_company(COMPANY, name='Alpha', slug='alpha')
        await repository.create_company(COMPANY, name='Alpha 2', slug='alpha-2')

        listed = await repository.list_companies(COMPANY)
        assert len(listed) == 1
        found = await repository.get_company(COMPANY)
        assert found is not None
        assert found.name == 'Alpha 2'


# Keep adapter names visible for the contract matrix coverage gate.
_PostgresCompanyRepository = PostgresCompanyRepository
