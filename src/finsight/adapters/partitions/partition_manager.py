"""Postgres adapter for per-company partition management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.partition_gateway import PartitionGateway

from ._partition_manager_shared import (
    DEFAULT_PARTITION_TABLES,
    _partition_name,  # noqa: F401
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.ports.partition_metadata_repository import (
        PartitionMetadataRepository,
    )


class PartitionManager(PartitionGateway):
    """Concrete partition manager using SQLAlchemy connections."""

    def __init__(
        self,
        session_or_engine: Any,
        metadata_repository: PartitionMetadataRepository | None = None,
        tables: list[str] | None = None,
    ) -> None:
        self._session_or_engine = session_or_engine
        self._metadata_repo = metadata_repository
        self._tables = tables or DEFAULT_PARTITION_TABLES

    async def _execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        from ._partition_manager__execute import _execute as _adapter_method

        await _adapter_method(self, sql, params)

    async def _fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        from ._partition_manager__fetch_one import _fetch_one as _adapter_method

        return await _adapter_method(self, sql, params)

    async def create_partition(self, company_id: CompanyId, table_name: str) -> str:
        from ._partition_manager_create_partition import _create_partition as _adapter_method

        return await _adapter_method(self, company_id, table_name)

    async def ensure_partition_exists(self, company_id: CompanyId, table_name: str) -> bool:
        from ._partition_manager_ensure_partition_exists import (
            _ensure_partition_exists as _adapter_method,
        )

        return await _adapter_method(self, company_id, table_name)

    async def drop_partition(self, company_id: CompanyId, table_name: str) -> bool:
        from ._partition_manager_drop_partition import _drop_partition as _adapter_method

        return await _adapter_method(self, company_id, table_name)

    async def list_partitions(self, company_id: CompanyId) -> list[str]:
        from ._partition_manager_list_partitions import _list_partitions as _adapter_method

        return await _adapter_method(self, company_id)

    async def record_partition_metadata(
        self,
        company_id: CompanyId,
        partition_name: str,
        table_name: str,
    ) -> None:
        from ._partition_manager_record_partition_metadata import (
            _record_partition_metadata as _adapter_method,
        )

        await _adapter_method(self, company_id, partition_name, table_name)


# Alias for compatibility

# Compatibility aliases (preserved for external imports)
PostgresPartitionManager = PartitionManager
