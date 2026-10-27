"""Postgres adapter for per-company partition management."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from finsight.core.types import CompanyId, PartitionStatus
from finsight.domain.ports.partition_gateway import PartitionGateway
from finsight.domain.ports.partition_metadata_repository import (
    PartitionMetadataRepository,
)

DEFAULT_PARTITION_TABLES = [
    'documents',
    'document_chunks',
    'metrics',
    'answers',
    'audit_logs',
]


def _partition_name(company_id: CompanyId, table_name: str) -> str:
    """Generate a deterministic partition name for a company and table."""
    # Use safe naming - postgres identifiers, company_id is uuid as string
    clean_id = str(company_id).replace('-', '')
    return f'{table_name}_company_{clean_id}'


class PostgresPartitionManager(PartitionGateway):
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
        session = self._session_or_engine
        # Support different session/engine patterns
        if hasattr(session, 'execute'):
            # Could be AsyncSession or Connection
            result = session.execute(text(sql), params or {})
            # Try to commit if it's a session
            if hasattr(session, 'commit'):
                try:
                    await session.commit()  # type: ignore[misc]
                except Exception:
                    pass
            return
        # Try getting a connection
        if hasattr(session, 'begin'):
            async with session.begin() as conn:  # type: ignore[attr-defined]
                await conn.execute(text(sql), params or {})
            return
        raise TypeError('Unsupported session/engine type')

    async def _fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        session = self._session_or_engine
        if hasattr(session, 'execute'):
            result = session.execute(text(sql), params or {})
            row = result.fetchone()
            if hasattr(session, 'commit'):
                try:
                    await session.commit()  # type: ignore[misc]
                except Exception:
                    pass
            return row
        if hasattr(session, 'begin'):
            async with session.begin() as conn:  # type: ignore[attr-defined]
                result = await conn.execute(text(sql), params or {})
                return result.fetchone()
        raise TypeError('Unsupported session/engine type')

    async def create_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> str:
        """Create a partition for a company on the given table."""
        partition_name = _partition_name(company_id, table_name)
        try:
            # Create partition
            await self._execute(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES IN (:company_id)
                """,
                {'company_id': str(company_id)},
            )
        except Exception:
            # Try alternative syntax if needed
            await self._execute(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES IN ('{company_id}')
                """
            )

        # Create indexes on partition
        try:
            if table_name == 'documents':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_status ON {partition_name} (company_id, status)'
                )
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_period ON {partition_name} (company_id, period_start, period_end)'
                )
            elif table_name == 'document_chunks':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_document ON {partition_name} (company_id, document_id)'
                )
                # Create HNSW vector index on partition if embedding exists
                try:
                    await self._execute(
                        f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_embedding_hnsw ON {partition_name} USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)'
                    )
                except Exception:
                    pass
            elif table_name == 'metrics':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_name_period ON {partition_name} (company_id, name, period_end)'
                )
            elif table_name == 'answers':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_question ON {partition_name} (company_id, question_id)'
                )
            elif table_name == 'audit_logs':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_id ON {partition_name} (company_id)'
                )
            else:
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_id ON {partition_name} (company_id)'
                )
        except Exception:
            pass

        # Record partition metadata
        if self._metadata_repo is not None:
            try:
                await self._metadata_repo.record_partition(
                    company_id=company_id,
                    partition_name=partition_name,
                    table_name=table_name,
                    status=PartitionStatus.CREATING,
                )
                try:
                    await self._metadata_repo.update_status(
                        company_id, table_name, PartitionStatus.READY
                    )
                except Exception:
                    pass
            except Exception:
                pass
        else:
            # Try to record directly if no repo provided
            try:
                await self._execute(
                    """
                    INSERT INTO partition_metadata (company_id, partition_name, table_name, status)
                    VALUES (:company_id, :partition_name, :table_name, 'creating')
                    ON CONFLICT (company_id, table_name) DO NOTHING
                    """,
                    {
                        'company_id': str(company_id),
                        'partition_name': partition_name,
                        'table_name': table_name,
                    },
                )
                try:
                    await self._execute(
                        """
                        UPDATE partition_metadata
                        SET status = 'ready', updated_at = now()
                        WHERE company_id = :company_id AND table_name = :table_name
                        """,
                        {'company_id': str(company_id), 'table_name': table_name},
                    )
                except Exception:
                    pass
            except Exception:
                pass

        return partition_name

    async def ensure_partition_exists(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> bool:
        """Ensure partition exists (idempotent)."""
        partition_name = _partition_name(company_id, table_name)
        # Check if partition exists
        try:
            row = await self._fetch_one(
                """
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = :partition_name AND n.nspname = 'public'
                """,
                {'partition_name': partition_name},
            )
            if row is not None:
                return True
        except Exception:
            pass

        # Create if not exists
        try:
            await self.create_partition(company_id, table_name)
            return True
        except Exception:
            return False

    async def drop_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> bool:
        """Drop a partition for a company."""
        partition_name = _partition_name(company_id, table_name)
        try:
            await self._execute(f'DROP TABLE IF EXISTS {partition_name} CASCADE')
            return True
        except Exception:
            return False

    async def list_partitions(
        self,
        company_id: CompanyId,
    ) -> list[str]:
        """List all partitions for a company."""
        try:
            # Look for partitions matching pattern
            result = self._session_or_engine.execute(
                text(
                    """
                    SELECT c.relname
                    FROM pg_inherits i
                    JOIN pg_class c ON c.oid = i.inhrelid
                    JOIN pg_class p ON p.oid = i.inhparent
                    JOIN pg_namespace n ON n.oid = p.relnamespace
                    WHERE n.nspname = 'public'
                    AND c.relname LIKE :pattern
                    """
                ),
                {'pattern': f'%company_{str(company_id).replace("-", "")}%'},
            )
            rows = result.fetchall()
            if hasattr(self._session_or_engine, 'commit'):
                try:
                    await self._session_or_engine.commit()  # type: ignore[misc]
                except Exception:
                    pass
            return [row[0] for row in rows]
        except Exception:
            return []

    async def record_partition_metadata(
        self,
        company_id: CompanyId,
        partition_name: str,
        table_name: str,
    ) -> None:
        """Record partition metadata."""
        if self._metadata_repo is not None:
            try:
                await self._metadata_repo.record_partition(
                    company_id=company_id,
                    partition_name=partition_name,
                    table_name=table_name,
                    status=PartitionStatus.READY,
                )
                return
            except Exception:
                pass
        try:
            await self._execute(
                """
                INSERT INTO partition_metadata (company_id, partition_name, table_name, status)
                VALUES (:company_id, :partition_name, :table_name, 'ready')
                ON CONFLICT (company_id, table_name) DO UPDATE SET status = 'ready', updated_at = now()
                """,
                {
                    'company_id': str(company_id),
                    'partition_name': partition_name,
                    'table_name': table_name,
                },
            )
        except Exception:
            pass


# Alias for compatibility
PartitionManager = PostgresPartitionManager
