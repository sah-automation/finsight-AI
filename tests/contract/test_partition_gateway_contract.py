"""Contract tests for the PartitionGateway port."""

from __future__ import annotations

import pytest

# Adapter aliases exercised: PartitionManager, PartitionGateway, PartitionManager.
from finsight.adapters.partitions.partition_manager import PartitionManager, _partition_name
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY_A = CompanyId('company-a')
COMPANY_B = CompanyId('company-b')


class FakeResult:
    def __init__(self, rows=None) -> None:
        self._rows = list(rows or [])

    def fetchone(self) -> object:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[object]:
        return list(self._rows)


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.partitions: list[str] = []

    def execute(self, statement: object, params: object = None) -> object:
        sql = str(statement)
        self.executed.append((sql, dict(params or {})))
        if 'pg_class' in sql or 'pg_inherits' in sql:
            return FakeResult([('documents_company_' + str(COMPANY_A).replace('-', ''),)])
        return FakeResult([])

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def begin(self) -> object:
        return self

    async def __aenter__(self) -> object:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def manager(session: FakeSession) -> PartitionManager:
    return PartitionManager(session_or_engine=session, metadata_repository=None, tables=[])


class TestPartitionGatewayContract:
    async def test_create_partition_returns_name(self, manager: PartitionManager) -> None:
        name = await manager.create_partition(COMPANY_A, 'documents')
        assert isinstance(name, str)
        assert 'company' in name
        assert str(COMPANY_A).replace('-', '') in name

    async def test_ensure_partition_exists_idempotent(self, manager: PartitionManager) -> None:
        first = await manager.ensure_partition_exists(COMPANY_A, 'documents')
        second = await manager.ensure_partition_exists(COMPANY_A, 'documents')
        assert first is True
        assert second is True

    async def test_drop_partition(self, manager: PartitionManager) -> None:
        result = await manager.drop_partition(COMPANY_A, 'documents')
        assert result is True

    async def test_list_partitions_returns_list(self, manager: PartitionManager) -> None:
        result = await manager.list_partitions(COMPANY_A)
        assert isinstance(result, list)

    async def test_record_partition_metadata(self, manager: PartitionManager) -> None:
        partition_name = _partition_name(COMPANY_A, 'documents')
        await manager.record_partition_metadata(COMPANY_A, partition_name, 'documents')

    async def test_company_scoping_in_name(self, manager: PartitionManager) -> None:
        name_a = await manager.create_partition(COMPANY_A, 'metrics')
        name_b = await manager.create_partition(COMPANY_B, 'metrics')
        assert name_a != name_b

    async def test_idempotent_create(self, manager: PartitionManager) -> None:
        first = await manager.create_partition(COMPANY_A, 'answers')
        second = await manager.create_partition(COMPANY_A, 'answers')
        assert first == second
