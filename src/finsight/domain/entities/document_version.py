"""DocumentVersion entity - per-version ingestion state machine (pure domain)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from finsight.core.errors import InvalidStateTransitionError

from ._document_version_init import (
    _init_document_version,
    _normalize_review_scope,
    _now,
)
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

    def __init__(self, *args: object, **kwargs: object) -> None:
        _init_document_version(self, *args, **kwargs)

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
