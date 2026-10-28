from __future__ import annotations

from typing import Any


class DeleteResult:
    """Result returned by :class:`DeleteDocument`."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        company_id: Any,
        document_id: Any = None,
        deleted: bool = False,
        soft_deleted: bool | None = None,
        restored: bool = False,
        purged: bool = False,
        permanent: bool = False,
        scheduled: bool = False,
        purge_scheduled: bool | None = None,
        purge_after_days: Any = None,
        deleted_retention_days: Any = None,
        retention_days: Any = None,
        audit_kept: bool = True,
        cache_cleared: bool = False,
        idempotent: bool = True,
        already_deleted: bool = False,
        status: Any = 'deleted',
        **extra: Any,
    ) -> None:
        self.company_id = company_id
        self.document_id = document_id
        self.deleted = bool(deleted)
        self.soft_deleted = self.deleted if soft_deleted is None else bool(soft_deleted)
        self.restored = bool(restored)
        self.purged = bool(purged)
        self.permanent = bool(permanent)
        self.purged_permanently = self.purged and self.permanent
        self.scheduled = bool(scheduled or purge_scheduled)
        self.purge_scheduled = self.scheduled if purge_scheduled is None else bool(purge_scheduled)
        self.purge_after_days = (
            purge_after_days if purge_after_days is not None else deleted_retention_days
        )
        if self.purge_after_days is None:
            self.purge_after_days = retention_days
        self.deleted_retention_days = deleted_retention_days
        self.retention_days = retention_days
        self.audit_kept = audit_kept
        self.cache_cleared = cache_cleared
        self.idempotent = idempotent
        self.already_deleted = already_deleted
        self.status = status
        for key, value in extra.items():
            setattr(self, key, value)


__all__ = ['DeleteResult']
