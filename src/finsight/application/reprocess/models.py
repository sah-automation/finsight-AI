from __future__ import annotations

from typing import Any


class ReprocessResult:
    """Result returned by :class:`Reprocess`."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        company_id: Any = None,
        company_ids: list[Any] | None = None,
        processed_companies: list[Any] | None = None,
        processed: list[Any] | None = None,
        companies: list[Any] | None = None,
        batches: list[Any] | None = None,
        batch_size: int = 3,
        batch_count: int = 1,
        priority: Any = 'low',
        queued: bool = False,
        enqueued: bool | None = None,
        job_id: Any = None,
        delta_tracking: bool | None = None,
        idempotent: bool = True,
        no_mixing: bool = True,
        never_mix: bool = True,
        atomic: bool = True,
        atomic_commit: bool = True,
        stays_on_current_version: bool = True,
        rolling: bool = True,
        status: Any = 'completed',
        cache_cleared: bool = False,
        published: bool = False,
        affected_documents: list[str] | None = None,
        **extra: Any,
    ) -> None:
        processed_list = (
            processed_companies
            if processed_companies is not None
            else (
                processed
                if processed is not None
                else (companies if companies is not None else (company_ids or []))
            )
        )
        if company_id is not None and not processed_list:
            processed_list = [company_id]
        company_ids_list = company_ids if company_ids is not None else list(processed_list)
        self.company_id = (
            company_id
            if company_id is not None
            else (processed_list[0] if processed_list else None)
        )
        self.company_ids = company_ids_list
        self.companies = processed_list
        self.processed = processed_list
        self.processed_companies = processed_list
        self.batches = batches or [processed_list]
        self.batch_size = batch_size
        self.batch_count = len(self.batches) if self.batches else batch_count
        self.priority = priority
        self.queued = bool(queued or enqueued)
        self.enqueued = self.queued if enqueued is None else enqueued
        self.job_id = job_id
        self.delta_tracking = delta_tracking
        self.idempotent = idempotent
        self.no_mixing = no_mixing
        self.never_mix = never_mix
        self.atomic = atomic
        self.atomic_commit = atomic_commit
        self.stays_on_current_version = stays_on_current_version
        self.rolling = rolling
        self.status = status
        self.cache_cleared = cache_cleared
        self.published = published
        self.affected_documents = list(affected_documents or [])
        for key, value in extra.items():
            setattr(self, key, value)


__all__ = ['ReprocessResult']
