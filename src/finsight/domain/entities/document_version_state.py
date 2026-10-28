"""DocumentVersion state enum."""

from __future__ import annotations


class DocumentVersionState(str):
    """String-backed state enum for a :class:`DocumentVersion`.

    Subclassing ``str`` (rather than ``StrEnum``) keeps construction from
    arbitrary strings cheap while still comparing equal to plain strings.
    """

    RECEIVED = 'received'
    STORED = 'stored'
    PROCESSING = 'processing'
    COMMITTED = 'committed'
    FAILED = 'failed'
    NEEDS_REVIEW = 'needs_review'
    SUPERSEDED = 'superseded'
    REJECTED = 'rejected'
    # ``done`` is an alias for ``committed`` (plan vocabulary).
    DONE = 'committed'

    def __new__(cls, value: object) -> DocumentVersionState:
        canonical = str(value).strip().lower() if value is not None else ''
        if canonical in {'done'}:
            canonical = 'committed'
        obj = str.__new__(cls, canonical)
        return obj

    @classmethod
    def normalize(cls, value: object) -> DocumentVersionState:
        if isinstance(value, DocumentVersionState):
            return value
        return cls(value)


# Backwards-compatible names for the state enum.
DocumentVersionStatus: type[DocumentVersionState] = DocumentVersionState
DocumentState: type[DocumentVersionState] = DocumentVersionState
DocumentVersionLifecycleState: type[DocumentVersionState] = DocumentVersionState
