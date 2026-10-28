"""DocumentVersion entity - per-version ingestion state machine (pure domain)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from finsight.core.errors import InvalidStateTransitionError

from .document_version_state import (
    DocumentState,
    DocumentVersionLifecycleState,
    DocumentVersionState,
    DocumentVersionStatus,
)

# Public alias names for the illegal-move error raised by this entity.
IllegalStateTransitionError = InvalidStateTransitionError
InvalidTransitionError = InvalidStateTransitionError
InvalidDocumentVersionTransitionError = InvalidStateTransitionError
DocumentVersionTransitionError = InvalidStateTransitionError


def _coalesce(kwargs: dict[str, object], *names: str, default: object = None) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    return default


def _now() -> datetime:
    return datetime.now(UTC)


_TRANSITIONS: dict[str, set[str]] = {
    DocumentVersionState.RECEIVED: {DocumentVersionState.STORED, DocumentVersionState.REJECTED},
    DocumentVersionState.STORED: {DocumentVersionState.PROCESSING},
    DocumentVersionState.PROCESSING: {
        DocumentVersionState.COMMITTED,
        DocumentVersionState.NEEDS_REVIEW,
        DocumentVersionState.FAILED,
    },
    DocumentVersionState.COMMITTED: {DocumentVersionState.SUPERSEDED},
}


@dataclass(init=False)
class DocumentVersion:
    """Per-version lifecycle state. Illegal moves raise ``InvalidStateTransitionError``.

    The fields below are plain attributes so transitions can mutate them.
    Keyword aliases are accepted for the common naming variants used across the
    project (for example ``status`` for ``state``).
    """

    id: object | None = None
    version_id: object | None = None
    document_version_id: object | None = None
    company_id: object | None = None
    document_id: object | None = None
    version: object | None = None
    version_number: object | None = None
    revision: object | None = None
    state: object | None = None
    status: object | None = None
    document_state: object | None = None
    document_status: object | None = None
    lifecycle_state: object | None = None
    filename: object | None = None
    file_name: object | None = None
    original_filename: object | None = None
    file_hash: object | None = None
    content_hash: object | None = None
    hash: object | None = None
    checksum: object | None = None
    category: object = None
    document_category: object = None
    review_scope: object | None = None
    needs_review_scope: object | None = None
    review_level: object | None = None
    review_kind: object | None = None
    scope: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, object] | None = None
    extras: dict[str, object] = field(default_factory=dict)

    def __init__(self, *args: object, **kwargs: object) -> None:  # noqa: PLR0912, PLR0915
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
                if getattr(self, key, None) is None:
                    setattr(self, key, value)

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
            self.id = ident
        if kwargs.get('version_id') is not None:
            self.version_id = kwargs.get('version_id')
        if kwargs.get('document_version_id') is not None:
            self.document_version_id = kwargs.get('document_version_id')

        self.company_id = _coalesce(
            kwargs, 'company_id', 'companyId', 'tenant_id', default=self.company_id
        )
        self.document_id = _coalesce(
            kwargs,
            'document_id',
            'documentId',
            'doc_id',
            'docId',
            'document',
            default=self.document_id,
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
                value = getattr(self, attr, None)
                if value is not None:
                    state_value = value
                    break
        if state_value is None:
            state_value = DocumentVersionState.RECEIVED
        state_value = DocumentVersionState.normalize(state_value)
        self.state = state_value
        self.status = state_value
        self.document_state = state_value
        self.document_status = state_value
        self.lifecycle_state = state_value

        # Identity scalar aliases kept in sync (mirrored fields).
        if self.version_id is None:
            self.version_id = self.id
        if self.document_version_id is None:
            self.document_version_id = self.id

        # Version number aliases.
        version_value = _coalesce(
            kwargs, 'version', 'version_number', 'revision', 'sequence', default=None
        )
        if version_value is None:
            for attr in ('version', 'version_number', 'revision'):
                value = getattr(self, attr, None)
                if value is not None:
                    version_value = value
                    break
        if version_value is None:
            version_value = 1
        self.version = version_value
        self.version_number = version_value
        self.revision = version_value

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
                value = getattr(self, attr, None)
                if value is not None:
                    filename_value = value
                    break
        self.filename = filename_value
        self.file_name = filename_value
        self.original_filename = filename_value or self.original_filename

        file_hash_value = _coalesce(
            kwargs, 'file_hash', 'content_hash', 'hash', 'checksum', default=None
        )
        if file_hash_value is None:
            for attr in ('file_hash', 'content_hash', 'hash', 'checksum'):
                value = getattr(self, attr, None)
                if value is not None:
                    file_hash_value = value
                    break
        self.file_hash = file_hash_value
        self.content_hash = file_hash_value
        self.hash = file_hash_value
        self.checksum = file_hash_value

        category_value = _coalesce(
            kwargs, 'category', 'document_category', 'doc_category', default=None
        )
        if category_value is None:
            category_value = getattr(self, 'category', None)
        self.category = category_value
        self.document_category = category_value

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
                value = getattr(self, attr, None)
                if value is not None:
                    review_value = value
                    break
        self.review_scope = _normalize_review_scope(review_value)
        self.needs_review_scope = self.review_scope
        self.review_level = self.review_scope
        self.review_kind = self.review_scope
        self.scope = self.review_scope

        self.created_at = (
            cast('datetime | None', _coalesce(kwargs, 'created_at', default=self.created_at))
            or self.created_at
        )
        self.updated_at = (
            cast('datetime | None', _coalesce(kwargs, 'updated_at', default=self.updated_at))
            or self.updated_at
        )
        self.metadata = cast(
            'dict[str, object] | None', _coalesce(kwargs, 'metadata', default=self.metadata)
        )
        extras = _coalesce(kwargs, 'extras', default=None)
        if isinstance(extras, dict):
            self.extras = dict(extras)

        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.version_id is None:
            self.version_id = self.id
        if self.document_version_id is None:
            self.document_version_id = self.id
        if self.created_at is None:
            self.created_at = _now()
        if self.updated_at is None:
            self.updated_at = self.created_at

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
                self.extras[key] = value

    def can_transition_to(self, target: object) -> bool:
        target = DocumentVersionState.normalize(target)
        current = DocumentVersionState.normalize(self.state)
        if target == current:
            return True
        return target in _TRANSITIONS.get(current, set())

    def transition_to(self, target: object, *, review_scope: object = None) -> DocumentVersion:
        target = DocumentVersionState.normalize(target)
        if target != DocumentVersionState.normalize(self.state) and not self.can_transition_to(
            target
        ):
            raise InvalidStateTransitionError(
                f'Cannot transition DocumentVersion {self.id!r} from {self.state!r} to {target!r}',
                details={'from': str(self.state), 'to': str(target)},
            )
        self.state = target
        self.status = target
        self.document_state = target
        self.document_status = target
        self.lifecycle_state = target
        if target == DocumentVersionState.NEEDS_REVIEW and review_scope is not None:
            scope = _normalize_review_scope(review_scope)
            self.review_scope = scope
            self.needs_review_scope = scope
            self.review_level = scope
            self.review_kind = scope
            self.scope = scope
        self.updated_at = _now()
        return self

    # Convenience transition helpers.
    def mark_received(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.RECEIVED)

    def mark_stored(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.STORED)

    def mark_rejected(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.REJECTED)

    def mark_processing(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.PROCESSING)

    def mark_committed(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.COMMITTED)

    def mark_failed(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.FAILED)

    def mark_needs_review(self, review_scope: object = None) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.NEEDS_REVIEW, review_scope=review_scope)

    def mark_superseded(self) -> DocumentVersion:
        return self.transition_to(DocumentVersionState.SUPERSEDED)

    # Aliases for the transition method.
    def transition(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def move_to(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def advance_to(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def change_state(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def set_state(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def set_status(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def update_state(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def to_state(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)

    def goto(self, target: object, *args: object, **kwargs: object) -> DocumentVersion:
        return self.transition_to(target, *args, **kwargs)


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


__all__ = [
    'DocumentState',
    'DocumentVersion',
    'DocumentVersionLifecycleState',
    'DocumentVersionState',
    'DocumentVersionStatus',
    'DocumentVersionTransitionError',
    'IllegalStateTransitionError',
    'InvalidDocumentVersionTransitionError',
    'InvalidStateTransitionError',
    'InvalidTransitionError',
]
