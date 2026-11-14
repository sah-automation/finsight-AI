from __future__ import annotations

from typing import Any

try:
    from finsight.application.ingest_document.models import UploadInput as UpdateInput
except Exception:  # pragma: no cover
    UpdateInput = object  # type: ignore[misc, assignment]


class UpdateResult:
    """Result returned by :class:`UpdateDocument`."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        company_id: Any,
        document_id: Any = None,
        version_id: Any = None,
        document_version: Any = None,
        version: Any = None,
        state: Any = 'received',
        status: Any = 'accepted',
        upload_url: Any = None,
        presigned_url: Any = None,
        url: Any = None,
        link: Any = None,
        key: Any = None,
        storage_key: Any = None,
        object_key: Any = None,
        s3_key: Any = None,
        bucket: Any = None,
        expires_in: Any = None,
        content_type: Any = None,
        duplicate: bool = False,
        is_duplicate: bool | None = None,
        suggested_document_id: Any = None,
        suggested_version_id: Any = None,
        enqueued: bool = False,
        queued: bool | None = None,
        queued_job: bool | None = None,
        job_id: Any = None,
        delta_tracking: bool | None = None,
        stamp: Any = None,
        document_stamp: Any = None,
        cache_cleared: bool = False,
        affected_documents: list[str] | None = None,
        metrics_recomputed: bool = False,
        published: bool = False,
        cascade_triggered: bool = False,
        partition_missing: bool = False,
        **extra: Any,
    ) -> None:
        self.company_id = company_id
        self.document_id = document_id
        self.version_id = version_id
        self.version = version if version is not None else version_id
        self.document_version = document_version if document_version is not None else self.version
        self.state = state
        self.status = status
        url_value = upload_url if upload_url is not None else presigned_url
        if url_value is None:
            url_value = url
        if url_value is None:
            url_value = link
        self.upload_url = url_value
        self.presigned_url = url_value if presigned_url is None else presigned_url
        if self.presigned_url is None:
            self.presigned_url = url_value
        self.url = url_value if url is None else url
        self.link = self.url if link is None else link
        self.key = key
        self.storage_key = storage_key if storage_key is not None else key
        self.object_key = object_key if object_key is not None else key
        self.s3_key = s3_key if s3_key is not None else key
        self.bucket = bucket
        self.expires_in = expires_in
        self.content_type = content_type
        self.duplicate = bool(duplicate or is_duplicate)
        self.is_duplicate = self.duplicate if is_duplicate is None else is_duplicate
        self.duplicated = self.duplicate
        self.duplicate_found = self.duplicate
        self.duplicate_detected = self.duplicate
        self.suggested_document_id = suggested_document_id
        self.suggested_version_id = suggested_version_id
        self.enqueued = bool(enqueued or queued or queued_job)
        self.queued = self.enqueued if queued is None else queued
        self.queued_job = self.enqueued if queued_job is None else queued_job
        self.job_id = job_id
        self.delta_tracking = delta_tracking
        stamp_value = stamp if stamp is not None else document_stamp
        self.stamp = stamp_value
        self.document_stamp = stamp_value
        self.cache_cleared = cache_cleared
        self.affected_documents = list(affected_documents or [])
        self.affected_count = len(self.affected_documents)
        self.metrics_recomputed = metrics_recomputed
        self.published = published
        self.cascade_triggered = cascade_triggered
        self.partition_missing = partition_missing
        for key_name, value in extra.items():
            setattr(self, key_name, value)


__all__ = ['UpdateInput', 'UpdateResult']
