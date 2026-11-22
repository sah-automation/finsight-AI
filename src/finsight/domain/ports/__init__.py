"""Domain ports."""

from __future__ import annotations

from .answer_cache import AnswerCache
from .audit_log import AuditLog
from .change_event_publisher import ChangeEventPublisher
from .chunk_repository import ChunkRepository
from .company_repository import CompanyRepository
from .document_reader import DocumentReader
from .document_repository import DocumentRepository
from .document_table_repository import DocumentTableRepository
from .embedding_provider import EmbeddingGateway, EmbeddingProvider, Embeddings
from .hybrid_search import HybridSearch, HybridSearchPort, VectorSearch
from .job_progress_port import JobProgressPort
from .job_repository import JobRepository
from .kpi_repository import KpiRepository, KpiRepositoryPort
from .llm_gateway import LLM, LLMGateway
from .metering_port import MeteringPort
from .metric_repository import MetricRepository, MetricsRepository
from .object_storage import ObjectStorage
from .observability_exporter_port import ObservabilityExporterPort
from .partition_gateway import PartitionGateway, PartitionManager
from .partition_metadata_repository import PartitionMetadataRepository
from .queue_port import Queue, QueuePort
from .reranker import Reranker, RerankerPort
from .secrets_provider import SecretsProvider
from .tracing_port import TracingPort
from .unit_of_work import UnitOfWork
from .user_repository import UserRepository
from .vector_store_port import VectorSearchPort, VectorStorePort, VectorWritePort
from .vector_write import VectorWrite
from .virus_scanner import VirusScanner
from .waiting_line import QueueLine, WaitingLine, WaitingLinePort

# Compatibility aliases.
DocumentTablesRepository = DocumentTableRepository
DocumentTablesRepositoryPort = DocumentTableRepository
TableRepository = DocumentTableRepository
TablesRepository = DocumentTableRepository

__all__ = [
    'LLM',
    'AnswerCache',
    'AuditLog',
    'ChangeEventPublisher',
    'ChunkRepository',
    'CompanyRepository',
    'DocumentReader',
    'DocumentRepository',
    'DocumentTableRepository',
    'DocumentTablesRepository',
    'DocumentTablesRepositoryPort',
    'EmbeddingGateway',
    'EmbeddingProvider',
    'Embeddings',
    'HybridSearch',
    'HybridSearchPort',
    'JobProgressPort',
    'JobRepository',
    'KpiRepository',
    'KpiRepositoryPort',
    'LLMGateway',
    'MeteringPort',
    'MetricRepository',
    'MetricsRepository',
    'ObjectStorage',
    'ObservabilityExporterPort',
    'PartitionGateway',
    'PartitionManager',
    'PartitionMetadataRepository',
    'Queue',
    'QueueLine',
    'QueuePort',
    'Reranker',
    'RerankerPort',
    'SecretsProvider',
    'TableRepository',
    'TablesRepository',
    'TracingPort',
    'UnitOfWork',
    'UserRepository',
    'VectorSearch',
    'VectorSearchPort',
    'VectorStorePort',
    'VectorWrite',
    'VectorWritePort',
    'VirusScanner',
    'WaitingLine',
    'WaitingLinePort',
]
