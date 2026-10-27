"""Postgres/Aurora partition metadata repository implementing the port."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from finsight.core.types import CompanyId, PartitionStatus
from finsight.domain.entities.partition_metadata import PartitionMetadata
from finsight.domain.ports.partition_metadata_repository import (
    PartitionMetadataRepository as PartitionMetadataRepositoryPort,
)

from .base_repository import BaseRepository

_TABLE = 'partition_metadata'


def _row_to_metadata(row: Any) -> PartitionMetadata | None:
    if row is None:
        return None
    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        company_id = mapping['company_id']
        partition_name = mapping['partition_name']
        table_name = mapping['table_name']
        status = mapping['status']
        created_at = mapping.get('created_at') if hasattr(mapping, 'get') else mapping['created_at']
        updated_at = mapping.get('updated_at') if hasattr(mapping, 'get') else mapping['updated_at']
    else:
        company_id, partition_name, table_name, status, created_at, updated_at = row[:6]
    return PartitionMetadata(
        company_id=CompanyId(str(company_id)),
        partition_name=str(partition_name),
        table_name=str(table_name),
        status=PartitionStatus(str(status)),
        created_at=created_at if isinstance(created_at, (datetime, type(None))) else None,
        updated_at=updated_at if isinstance(updated_at, (datetime, type(None))) else None,
    )


class PartitionMetadataRepository(PartitionMetadataRepositoryPort, BaseRepository):
    """Concrete partition metadata repository with RLS context enforcement."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)

    async def record_partition(
        self,
        company_id: CompanyId,
        partition_name: str,
        table_name: str,
        status: PartitionStatus = PartitionStatus.CREATING,
    ) -> PartitionMetadata:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            INSERT INTO {_TABLE} (company_id, partition_name, table_name, status)
            VALUES (:company_id, :partition_name, :table_name, :status)
            ON CONFLICT (company_id, table_name) DO UPDATE
                SET partition_name = EXCLUDED.partition_name,
                    status = EXCLUDED.status,
                    updated_at = now()
            RETURNING company_id, partition_name, table_name, status, created_at, updated_at
            """,
            {
                'company_id': str(company_id),
                'partition_name': partition_name,
                'table_name': table_name,
                'status': str(status),
            },
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        metadata = _row_to_metadata(row)
        if metadata is None:
            return PartitionMetadata(
                company_id=company_id,
                partition_name=partition_name,
                table_name=table_name,
                status=status,
            )
        return metadata

    async def get_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> PartitionMetadata | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT company_id, partition_name, table_name, status, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id AND table_name = :table_name
            """,
            {'company_id': str(company_id), 'table_name': table_name},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_metadata(row)

    async def list_partitions_for_company(
        self,
        company_id: CompanyId,
    ) -> list[PartitionMetadata]:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            SELECT company_id, partition_name, table_name, status, created_at, updated_at
            FROM {_TABLE}
            WHERE company_id = :company_id
            """,
            {'company_id': str(company_id)},
        )
        rows = result.fetchall() if hasattr(result, 'fetchall') else list(result) if result is not None else []
        metadata: list[PartitionMetadata] = []
        for row in rows:
            entry = _row_to_metadata(row)
            if entry is not None:
                metadata.append(entry)
        return metadata

    async def update_status(
        self,
        company_id: CompanyId,
        table_name: str,
        status: PartitionStatus,
    ) -> PartitionMetadata | None:
        await self._set_rls_context(company_id)
        result = await self._execute(
            f"""
            UPDATE {_TABLE}
            SET status = :status, updated_at = now()
            WHERE company_id = :company_id AND table_name = :table_name
            RETURNING company_id, partition_name, table_name, status, created_at, updated_at
            """,
            {'company_id': str(company_id), 'table_name': table_name, 'status': str(status)},
        )
        row = result.fetchone() if hasattr(result, 'fetchone') else None
        return _row_to_metadata(row)


PostgresPartitionMetadataRepository = PartitionMetadataRepository
PartitionMetadataRepositoryAdapter = PostgresPartitionMetadataRepository
PostgresPartitionMetadataRepo = PostgresPartitionMetadataRepository
RLSPartitionMetadataRepository = PartitionMetadataRepository
PartitionMetadataRepo = PostgresPartitionMetadataRepository

__all__ = [
    'PostgresPartitionMetadataRepository',
    'PartitionMetadataRepository',
    'PartitionMetadataRepositoryAdapter',
    'PostgresPartitionMetadataRepo',
    'RLSPartitionMetadataRepository',
    'PartitionMetadataRepo',
]
