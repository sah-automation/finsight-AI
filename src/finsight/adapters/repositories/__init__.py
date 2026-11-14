"""Repository adapters (Aurora/Postgres document, chunk, metric, job and tenant data)."""

from .base_repository import BaseRepository
from .postgres_chunk_repository import (
    AuroraChunkRepository,
    ChunkRepo,
    ChunkRepositoryAdapter,
    PostgresChunkRepo,
    PostgresChunkRepository,
    RLSChunkRepository,
)
from .postgres_document_repository import (
    AuroraDocumentRepository,
    DocumentRepo,
    DocumentRepositoryAdapter,
    PostgresDocumentRepo,
    PostgresDocumentRepository,
    RLSDocumentRepository,
)
from .postgres_document_table_repository import (
    AuroraDocumentTableRepository,
    DocumentTableRepositoryAdapter,
    PostgresDocumentTableRepo,
    PostgresDocumentTableRepository,
    PostgresDocumentTablesRepo,
    PostgresDocumentTablesRepository,
    RLSDocumentTableRepository,
)
from .postgres_metric_repository import (
    AuroraMetricRepository,
    MetricRepositoryAdapter,
    PostgresMetricRepo,
    PostgresMetricRepository,
    RLSMetricRepository,
)

__all__ = [
    'AuroraChunkRepository',
    'AuroraDocumentRepository',
    'AuroraDocumentTableRepository',
    'AuroraMetricRepository',
    'BaseRepository',
    'ChunkRepo',
    'ChunkRepositoryAdapter',
    'DocumentRepo',
    'DocumentRepositoryAdapter',
    'DocumentTableRepositoryAdapter',
    'MetricRepositoryAdapter',
    'PostgresChunkRepo',
    'PostgresChunkRepository',
    'PostgresDocumentRepo',
    'PostgresDocumentRepository',
    'PostgresDocumentTableRepo',
    'PostgresDocumentTableRepository',
    'PostgresDocumentTablesRepo',
    'PostgresDocumentTablesRepository',
    'PostgresMetricRepo',
    'PostgresMetricRepository',
    'RLSChunkRepository',
    'RLSDocumentRepository',
    'RLSDocumentTableRepository',
    'RLSMetricRepository',
]
