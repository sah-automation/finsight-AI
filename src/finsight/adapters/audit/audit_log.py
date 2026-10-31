"""Compatibility re-export of the audit log adapter."""

from .postgres_audit_log import PostgresAuditLog

AuditLog = PostgresAuditLog
PostgresAuditLogRepository = PostgresAuditLog
PostgresAuditLogger = PostgresAuditLog
AuditLogAdapter = PostgresAuditLog
AuroraAuditLog = PostgresAuditLog
AuditRepository = PostgresAuditLog
AuditLogger = PostgresAuditLog

__all__ = [
    'AuditLog',
    'AuditLogAdapter',
    'AuditLogger',
    'AuditRepository',
    'AuroraAuditLog',
    'PostgresAuditLog',
    'PostgresAuditLogRepository',
    'PostgresAuditLogger',
]
