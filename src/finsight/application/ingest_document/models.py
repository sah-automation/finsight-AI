"""Data shapes for the upload application use case."""

from __future__ import annotations

from typing import Any


class UploadStatus(str):
    """Status strings for an upload request."""

    ACCEPTED = 'accepted'
    CREATED = 'created'
    DUPLICATE = 'duplicate'
    PARTITION_MISSING = 'partition_missing'

    def __new__(cls, value: object = 'accepted') -> UploadStatus:
        return str.__new__(cls, str(value).strip().lower() if value is not None else 'accepted')


class UploadInput:
    """Input DTO. Accepts many common field names/aliases."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.company_id: Any = None
        self.document_category: Any = None
        self.category: Any = None
        self.period: Any = None
        self.status: Any = None
        self.document_status: Any = None
        self.upload_type: Any = None
        self.type: Any = None
        self.replaces_document_id: Any = None
        self.replaces: Any = None
        self.file: Any = None
        self.filename: Any = None
        self.file_name: Any = None
        self.file_hash: Any = None
        self.content_hash: Any = None
        self.hash: Any = None

        positional = (
            'company_id',
            'document_category',
            'period',
            'status',
            'upload_type',
            'replaces_document_id',
            'file',
            'file_hash',
        )
        for index, value in enumerate(args):
            if index < len(positional):
                setattr(self, positional[index], value)

        alias_map: dict[str, tuple[str, ...]] = {
            'company_id': ('companyId', 'company', 'tenant_id', 'tenantId'),
            'document_category': ('documentCategory', 'category', 'doc_category', 'document_type'),
            'period': ('reporting_period', 'period_label'),
            'status': ('document_status', 'state'),
            'upload_type': ('uploadType', 'type', 'action'),
            'replaces_document_id': ('replacesDocumentId', 'replace_document_id', 'replaces'),
            'file': ('files', 'filename', 'file_name', 'document', 'documents'),
            'file_hash': ('content_hash', 'hash', 'checksum'),
        }

        for canonical, aliases in alias_map.items():
            if canonical in kwargs and kwargs[canonical] is not None:
                setattr(self, canonical, kwargs[canonical])
            else:
                for alias in aliases:
                    if alias in kwargs and kwargs[alias] is not None:
                        setattr(self, canonical, kwargs[alias])
                        break

        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

        self.category = self.document_category if self.category is None else self.category
        self.document_category = self.document_category or self.category
        self.document_status = self.status
        self.type = self.upload_type
        self.upload_type = self.upload_type or self.type
        self.replaces = self.replaces_document_id
        self.replaces_document_id = self.replaces_document_id or self.replaces
        if self.filename is None:
            self.filename = self.file if isinstance(self.file, str) else self.file_name
        self.file_name = self.filename
        self.content_hash = self.file_hash or self.content_hash
        self.hash = self.file_hash or self.hash
        self.file_hash = self.content_hash or self.hash


class UploadResult:
    """Result of an upload request."""

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
        duplicated: bool | None = None,
        duplicate_found: bool | None = None,
        duplicate_detected: bool | None = None,
        suggest_update: bool = False,
        update_suggestion: bool | None = None,
        suggested_update: bool | None = None,
        suggested_action: Any = None,
        suggested_document_id: Any = None,
        suggested_version_id: Any = None,
        presigned_upload: Any = None,
        partition_missing: bool = False,
        **extra: Any,
    ) -> None:
        self.company_id = company_id
        self.document_id = document_id
        self.version_id = version_id
        self.version = version if version is not None else version_id
        self.document_version = document_version if document_version is not None else version
        self.state = state
        self.status = status
        self.upload_status = status
        renewable_url = presigned_upload if presigned_upload is not None else upload_url
        if renewable_url is None:
            renewable_url = presigned_url
        if renewable_url is None:
            renewable_url = url
        if renewable_url is None:
            renewable_url = link
        self.upload_url = renewable_url
        self.presigned_url = renewable_url if presigned_url is None else presigned_url
        if self.presigned_url is None:
            self.presigned_url = renewable_url
        self.url = self.presigned_url if url is None else url
        self.link = self.url if link is None else link
        self.key = key
        self.storage_key = storage_key if storage_key is not None else key
        self.object_key = object_key if object_key is not None else key
        self.s3_key = s3_key if s3_key is not None else key
        if presigned_upload is not None:
            try:
                self.key = getattr(presigned_upload, 'key', self.key)
                self.storage_key = getattr(presigned_upload, 'key', self.storage_key)
                self.object_key = getattr(presigned_upload, 'key', self.object_key)
                self.s3_key = getattr(presigned_upload, 'key', self.s3_key)
            except Exception:
                pass
        self.bucket = bucket
        self.expires_in = expires_in
        self.content_type = content_type
        self.presigned_upload = presigned_upload
        found = bool(
            duplicate or is_duplicate or duplicated or duplicate_found or duplicate_detected
        )
        self.duplicate = found
        self.is_duplicate = found if is_duplicate is None else is_duplicate
        self.duplicated = found if duplicated is None else duplicated
        self.duplicate_found = found if duplicate_found is None else duplicate_found
        self.duplicate_detected = found if duplicate_detected is None else duplicate_detected
        self.suggest_update = bool(suggest_update or update_suggestion or suggested_update or found)
        self.update_suggestion = (
            self.suggest_update if update_suggestion is None else update_suggestion
        )
        self.suggested_update = (
            self.suggest_update if suggested_update is None else suggested_update
        )
        self.suggested_action = suggested_action or ('update' if self.suggest_update else None)
        self.suggested_document_id = suggested_document_id
        self.suggested_version_id = suggested_version_id
        self.partition_missing = partition_missing
        for key_name, value in extra.items():
            setattr(self, key_name, value)

    @property
    def company_id_str(self) -> str:
        return str(self.company_id)

    @property
    def document_version_id(self) -> Any:
        if self.document_version is None:
            return None
        for attr in ('id', 'version_id', 'document_version_id'):
            value = getattr(self.document_version, attr, None)
            if value is not None:
                return value
        return self.version_id


UploadRequest = UploadInput
UploadCommand = UploadInput
UploadInputData = UploadInput
UploadPayload = UploadInput

UploadResponse = UploadResult
UploadOutput = UploadResult
UploadOutputResult = UploadResult
UploadSummary = UploadResult
UploadOutcome = UploadResult
PresignedUploadResult = UploadResult
UploadCreationResult = UploadResult
VersionCreationResult = UploadResult
DocumentVersionCreationResult = UploadResult
UploadLinkResult = UploadResult


__all__ = [
    'DocumentVersionCreationResult',
    'PresignedUploadResult',
    'UploadCommand',
    'UploadCreationResult',
    'UploadInput',
    'UploadInputData',
    'UploadLinkResult',
    'UploadOutcome',
    'UploadOutput',
    'UploadPayload',
    'UploadRequest',
    'UploadResponse',
    'UploadResult',
    'UploadStatus',
    'UploadSummary',
    'VersionCreationResult',
]
