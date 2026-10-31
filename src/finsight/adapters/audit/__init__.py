"""Audit adapters implementing the ``AuditLog`` port."""

from .postgres_audit_log import PostgresAuditLog

__all__ = ['PostgresAuditLog']
