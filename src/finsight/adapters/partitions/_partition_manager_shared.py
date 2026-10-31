"""Shared helpers for PartitionManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

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
