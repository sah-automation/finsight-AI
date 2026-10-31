"""Initialization helper for :class:`DocumentVersion`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from .document_version_state import DocumentVersionState


def _coalesce(kwargs: dict[str, object], *names: str, default: object = None) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    return default


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_review_scope(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace('-', '_').replace(' ', '_')
    if text in {'', 'none', 'null'}:
        return None
    if text in {'chunk', 'chunk_level', 'chunked', 'partial'}:
        return 'chunk'
    if text in {'document', 'whole', 'whole_document', 'full', 'global'}:
        return 'whole_document'
    return text


def _init_document_version(instance: Any, *args: object, **kwargs: object) -> None:  # noqa: ANN401, PLR0912, PLR0915
    positional_order = [
        'id',
        'company_id',
        'document_id',
        'state',
        'version',
        'filename',
        'file_hash',
        'category',
        'review_scope',
        'created_at',
        'updated_at',
    ]

    for index, value in enumerate(args):
        if index < len(positional_order):
            key = positional_order[index]
            if getattr(instance, key, None) is None:
                setattr(instance, key, value)

    # Scalar identity aliases.
    ident = _coalesce(
        kwargs,
        'id',
        'version_id',
        'document_version_id',
        'versionId',
        'documentVersionId',
        default=None,
    )
    if ident is not None:
        instance.id = ident
    if kwargs.get('version_id') is not None:
        instance.version_id = kwargs.get('version_id')
    if kwargs.get('document_version_id') is not None:
        instance.document_version_id = kwargs.get('document_version_id')

    instance.company_id = _coalesce(
        kwargs, 'company_id', 'companyId', 'tenant_id', default=instance.company_id
    )
    instance.document_id = _coalesce(
        kwargs,
        'document_id',
        'documentId',
        'doc_id',
        'docId',
        'document',
        default=instance.document_id,
    )

    # State/status aliases.
    state_value = _coalesce(
        kwargs,
        'state',
        'status',
        'document_state',
        'document_status',
        'lifecycle_state',
        default=None,
    )
    if state_value is None:
        # fall back to any already set scalar attribute
        for attr in ('state', 'status', 'document_state', 'document_status', 'lifecycle_state'):
            value = getattr(instance, attr, None)
            if value is not None:
                state_value = value
                break
    if state_value is None:
        state_value = DocumentVersionState.RECEIVED
    state_value = DocumentVersionState.normalize(state_value)
    instance.state = state_value
    instance.status = state_value
    instance.document_state = state_value
    instance.document_status = state_value
    instance.lifecycle_state = state_value

    # Identity scalar aliases kept in sync (mirrored fields).
    if instance.version_id is None:
        instance.version_id = instance.id
    if instance.document_version_id is None:
        instance.document_version_id = instance.id

    # Version number aliases.
    version_value = _coalesce(
        kwargs, 'version', 'version_number', 'revision', 'sequence', default=None
    )
    if version_value is None:
        for attr in ('version', 'version_number', 'revision'):
            value = getattr(instance, attr, None)
            if value is not None:
                version_value = value
                break
    if version_value is None:
        version_value = 1
    instance.version = version_value
    instance.version_number = version_value
    instance.revision = version_value

    # File metadata aliases.
    filename_value = _coalesce(
        kwargs,
        'filename',
        'file_name',
        'name',
        'original_filename',
        'source_filename',
        default=None,
    )
    if filename_value is None:
        for attr in ('filename', 'file_name', 'original_filename'):
            value = getattr(instance, attr, None)
            if value is not None:
                filename_value = value
                break
    instance.filename = filename_value
    instance.file_name = filename_value
    instance.original_filename = filename_value or instance.original_filename

    file_hash_value = _coalesce(
        kwargs, 'file_hash', 'content_hash', 'hash', 'checksum', default=None
    )
    if file_hash_value is None:
        for attr in ('file_hash', 'content_hash', 'hash', 'checksum'):
            value = getattr(instance, attr, None)
            if value is not None:
                file_hash_value = value
                break
    instance.file_hash = file_hash_value
    instance.content_hash = file_hash_value
    instance.hash = file_hash_value
    instance.checksum = file_hash_value

    category_value = _coalesce(
        kwargs, 'category', 'document_category', 'doc_category', default=None
    )
    if category_value is None:
        category_value = getattr(instance, 'category', None)
    instance.category = category_value
    instance.document_category = category_value

    review_value = _coalesce(
        kwargs,
        'review_scope',
        'needs_review_scope',
        'review_level',
        'review_kind',
        'scope',
        default=None,
    )
    if review_value is None:
        for attr in (
            'review_scope',
            'needs_review_scope',
            'review_level',
            'review_kind',
            'scope',
        ):
            value = getattr(instance, attr, None)
            if value is not None:
                review_value = value
                break
    instance.review_scope = _normalize_review_scope(review_value)
    instance.needs_review_scope = instance.review_scope
    instance.review_level = instance.review_scope
    instance.review_kind = instance.review_scope
    instance.scope = instance.review_scope

    instance.created_at = (
        cast('datetime | None', _coalesce(kwargs, 'created_at', default=instance.created_at))
        or instance.created_at
    )
    instance.updated_at = (
        cast('datetime | None', _coalesce(kwargs, 'updated_at', default=instance.updated_at))
        or instance.updated_at
    )
    instance.metadata = cast(
        'dict[str, object] | None', _coalesce(kwargs, 'metadata', default=instance.metadata)
    )
    extras = _coalesce(kwargs, 'extras', default=None)
    if isinstance(extras, dict):
        instance.extras = dict(extras)

    if instance.id is None:
        instance.id = str(uuid.uuid4())
    if instance.version_id is None:
        instance.version_id = instance.id
    if instance.document_version_id is None:
        instance.document_version_id = instance.id
    if instance.created_at is None:
        instance.created_at = _now()
    if instance.updated_at is None:
        instance.updated_at = instance.created_at

    # Store any extra keyword arguments in ``extras`` for forward compatibility.
    known = {
        'id',
        'version_id',
        'document_version_id',
        'versionId',
        'documentVersionId',
        'company_id',
        'companyId',
        'tenant_id',
        'document_id',
        'documentId',
        'doc_id',
        'docId',
        'document',
        'state',
        'status',
        'document_state',
        'document_status',
        'lifecycle_state',
        'version',
        'version_number',
        'revision',
        'sequence',
        'filename',
        'file_name',
        'name',
        'original_filename',
        'source_filename',
        'file_hash',
        'content_hash',
        'hash',
        'checksum',
        'category',
        'document_category',
        'doc_category',
        'review_scope',
        'needs_review_scope',
        'review_level',
        'review_kind',
        'scope',
        'created_at',
        'updated_at',
        'metadata',
        'extras',
    }
    for key, value in kwargs.items():
        if key not in known:
            instance.extras[key] = value
