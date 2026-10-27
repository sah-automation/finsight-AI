# Core Types - Shared IDs, enums, and type definitions

from __future__ import annotations

from enum import StrEnum
from typing import NewType

# ============================================================
# Strongly-typed IDs (NewType for static checking, runtime is str)
# ============================================================

CompanyId = NewType('CompanyId', str)
UserId = NewType('UserId', str)
DocumentId = NewType('DocumentId', str)
ChunkId = NewType('ChunkId', str)
JobId = NewType('JobId', str)
MetricId = NewType('MetricId', str)
AnswerId = NewType('AnswerId', str)
RecommendationId = NewType('RecommendationId', str)
ReportId = NewType('ReportId', str)
TraceId = NewType('TraceId', str)
SessionId = NewType('SessionId', str)


# ============================================================
# Enums
# ============================================================


class Role(StrEnum):
    """User roles in the system (exactly 4 roles)."""

    EXECUTIVE_LEADERSHIP = 'executive_leadership'
    CORPORATE_FINANCE_PLANNERS = 'corporate_finance_planners'
    AUDIT_COMPLIANCE = 'audit_compliance'
    SYSTEM_ADMIN = 'system_admin'


class DocumentCategory(StrEnum):
    """Document categories (exactly 6 categories)."""

    INVOICE = 'invoice'
    BANK_STATEMENT = 'bank_statement'
    FINANCIAL_STATEMENT = 'financial_statement'
    BUDGET = 'budget'
    CONTRACT = 'contract'
    BOARD_REPORT = 'board_report'


class DocumentStatus(StrEnum):
    """Document lifecycle status."""

    UPLOADING = 'uploading'
    PROCESSING = 'processing'
    COMMITTED = 'committed'
    FAILED = 'failed'
    DELETED = 'deleted'
    PURGED = 'purged'


class JobStatus(StrEnum):
    """Ingestion job status."""

    QUEUED = 'queued'
    PROCESSING = 'processing'
    COMMITTED = 'committed'
    FAILED = 'failed'
    RETRYING = 'retrying'


class Action(StrEnum):
    """Permission actions."""

    READ = 'read'
    WRITE = 'write'
    DELETE = 'delete'
    APPROVE = 'approve'
    UPLOAD = 'upload'
    UPDATE = 'update'
    RESTORE = 'restore'
    PURGE = 'purge'
    MANAGE_USERS = 'manage_users'
    MANAGE_SETTINGS = 'manage_settings'
    VIEW_AUDIT_LOG = 'view_audit_log'
    ADMIN = 'admin'


class UploadType(StrEnum):
    """Document upload types - only new and update (delete via lifecycle)."""

    NEW = 'new'
    UPDATE = 'update'


__all__ = [
    'Action',
    'AnswerId',
    'ChunkId',
    'CompanyId',
    'DocumentCategory',
    'DocumentId',
    'DocumentStatus',
    'JobId',
    'JobStatus',
    'MetricId',
    'RecommendationId',
    'ReportId',
    'Role',
    'SessionId',
    'TraceId',
    'UploadType',
    'UserId',
]
