"""Compatibility alias for AuroraDocumentTableRepository."""

from .postgres_document_table_repository import (
    PostgresDocumentTableRepository as AuroraDocumentTableRepository,
)

__all__ = ['AuroraDocumentTableRepository']
