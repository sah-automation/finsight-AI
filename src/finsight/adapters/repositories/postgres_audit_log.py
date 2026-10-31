"""Compatibility re-export of the audit log adapter."""

from finsight.adapters.audit.postgres_audit_log import PostgresAuditLog

AuditLog = PostgresAuditLog
PostgresAuditLogRepository = PostgresAuditLog
PostgresAuditLogger = PostgresAuditLog
PostgresAuditRepository = PostgresAuditLog
AuditLogAdapter = PostgresAuditLog
AuroraAuditLog = PostgresAuditLog
AuroraAuditLogRepository = PostgresAuditLog
AuditRepository = PostgresAuditLog
AuditLogger = PostgresAuditLog

__all__ = [
    'AuditLog',
    'AuditLogAdapter',
    'AuditLogger',
    'AuditRepository',
    'AuroraAuditLog',
    'AuroraAuditLogRepository',
    'PostgresAuditLog',
    'PostgresAuditLogRepository',
    'PostgresAuditLogger',
    'PostgresAuditRepository',
]
