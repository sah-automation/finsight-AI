"""Postgres adapter for per-company partition management."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from finsight.core.types import CompanyId, PartitionStatus
from finsight.domain.ports.partition_gateway import PartitionGateway

if TYPE_CHECKING:
    from finsight.domain.ports.partition_metadata_repository import (
        PartitionMetadataRepository,
    )

DEFAULT_PARTITION_TABLES = [
    'documents',
    'document_versions',
    'document_chunks',
    'document_tables',
    'metrics',
    'answers',
    'audit_logs',
    'jobs',
]


def _partition_name(company_id: CompanyId, table_name: str) -> str:
    """Generate a deterministic partition name for a company and table."""
    # Use safe naming - postgres identifiers, company_id is uuid as string
    clean_id = str(company_id).replace('-', '')
    return f'{table_name}_company_{clean_id}'


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
        import inspect

        session = self._session_or_engine
        # Support different session/engine patterns
        if hasattr(session, 'execute'):
            # Could be AsyncSession or Connection (sync or async)
            try:
                result = session.execute(text(sql), params or {})
                if inspect.isawaitable(result):
                    result = await result
                # Try to commit if it's a session
                if hasattr(session, 'commit'):
                    try:
                        commit_result = session.commit()
                        if inspect.isawaitable(commit_result):
                            await commit_result
                    except Exception:
                        pass
                return
            except Exception:
                # Reset any aborted transaction so later calls can proceed.
                if hasattr(session, 'rollback'):
                    try:
                        rollback_result = session.rollback()
                        if inspect.isawaitable(rollback_result):
                            await rollback_result
                    except Exception:
                        pass
                raise
        # Try getting a connection
        if hasattr(session, 'begin'):
            try:
                async_cm = session.begin()
                async with async_cm as conn:
                    result = conn.execute(text(sql), params or {})
                    if inspect.isawaitable(result):
                        await result
                return
            except Exception:
                raise
        raise TypeError('Unsupported session/engine type')

    async def _fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        import inspect

        session = self._session_or_engine
        if hasattr(session, 'execute'):
            result = session.execute(text(sql), params or {})
            if inspect.isawaitable(result):
                result = await result
            fetch = getattr(result, 'fetchone', None)
            if callable(fetch):
                row = fetch()
                if inspect.isawaitable(row):
                    row = await row
            else:
                row = result
            if hasattr(session, 'commit'):
                try:
                    commit_result = session.commit()
                    if inspect.isawaitable(commit_result):
                        await commit_result
                except Exception:
                    pass
            return row
        if hasattr(session, 'begin'):
            async_cm = session.begin()
            async with async_cm as conn:
                result = conn.execute(text(sql), params or {})
                if inspect.isawaitable(result):
                    result = await result
                fetch = getattr(result, 'fetchone', None)
                if callable(fetch):
                    row = fetch()
                    if inspect.isawaitable(row):
                        row = await row
                    return row
                return result.fetchone() if hasattr(result, 'fetchone') else result
        raise TypeError('Unsupported session/engine type')

    async def create_partition(
        self,
        company_id: CompanyId,
        table_name: str,
    ) -> str:
        """Create a partition for a company on the given table."""
        partition_name = _partition_name(company_id, table_name)
        try:
            # Create partition (bound value must be a literal in PostgreSQL)
            await self._execute(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES IN ('{company_id}')
                """
            )
        except Exception:
            # Partition may already exist; ignore.
            pass

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
                with contextlib.suppress(Exception):
                    await self._execute(
                        f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_embedding_hnsw ON {partition_name} USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)'
                    )
            elif table_name == 'metrics':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_name_period ON {partition_name} (company_id, name, period_end)'
                )
            elif table_name == 'answers':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_created ON {partition_name} (company_id, created_at)'
                )
            elif table_name == 'document_versions':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_document ON {partition_name} (company_id, document_id)'
                )
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_state ON {partition_name} (company_id, state)'
                )
            elif table_name == 'jobs':
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_status ON {partition_name} (company_id, status)'
                )
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_created ON {partition_name} (company_id, created_at)'
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
                with contextlib.suppress(Exception):
                    await self._metadata_repo.update_status(
                        company_id, table_name, PartitionStatus.READY
                    )
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
                with contextlib.suppress(Exception):
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
            import inspect

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
            if inspect.isawaitable(result):
                result = await result
            rows = result.fetchall() if hasattr(result, 'fetchall') else list(result or [])
            if inspect.isawaitable(rows):
                rows = await rows
            if hasattr(self._session_or_engine, 'commit'):
                try:
                    commit_result = self._session_or_engine.commit()
                    if inspect.isawaitable(commit_result):
                        await commit_result
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
        with contextlib.suppress(Exception):
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


# Alias for compatibility
PostgresPartitionManager = PartitionManager
