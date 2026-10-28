"""Domain ports."""

from __future__ import annotations

from .answer_cache import AnswerCache
from .company_repository import CompanyRepository
from .document_reader import DocumentReader
from .document_repository import DocumentRepository
from .job_repository import JobRepository
from .object_storage import ObjectStorage
from .partition_gateway import PartitionGateway, PartitionManager
from .partition_metadata_repository import PartitionMetadataRepository
from .unit_of_work import UnitOfWork
from .user_repository import UserRepository
from .virus_scanner import VirusScanner

__all__ = [
    'AnswerCache',
    'CompanyRepository',
    'DocumentReader',
    'DocumentRepository',
    'JobRepository',
    'ObjectStorage',
    'PartitionGateway',
    'PartitionManager',
    'PartitionMetadataRepository',
    'UnitOfWork',
    'UserRepository',
    'VirusScanner',
]
