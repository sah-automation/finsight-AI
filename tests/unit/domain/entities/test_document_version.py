from __future__ import annotations

import pytest

from finsight.core.errors import InvalidStateTransitionError
from finsight.domain.entities import DocumentVersion, DocumentVersionState


def test_received_to_stored_to_processing_to_committed() -> None:
    version = DocumentVersion(state=DocumentVersionState.RECEIVED)
    version.mark_stored()
    assert version.state == DocumentVersionState.STORED
    version.mark_processing()
    assert version.state == DocumentVersionState.PROCESSING
    version.mark_committed()
    assert version.state == DocumentVersionState.COMMITTED


def test_received_to_rejected_terminal() -> None:
    version = DocumentVersion(state=DocumentVersionState.RECEIVED)
    version.mark_rejected()
    assert version.state == DocumentVersionState.REJECTED


def test_received_to_failed_is_invalid() -> None:
    version = DocumentVersion(state=DocumentVersionState.RECEIVED)
    with pytest.raises(InvalidStateTransitionError):
        version.mark_failed()


def test_stored_to_committed_is_invalid() -> None:
    version = DocumentVersion(state=DocumentVersionState.STORED)
    with pytest.raises(InvalidStateTransitionError):
        version.mark_committed()


def test_processing_to_failed_then_terminal() -> None:
    version = DocumentVersion(state=DocumentVersionState.PROCESSING)
    version.mark_failed()
    assert version.state == DocumentVersionState.FAILED
    with pytest.raises(InvalidStateTransitionError):
        version.mark_processing()


def test_committed_to_superseded_allowed() -> None:
    version = DocumentVersion(state=DocumentVersionState.COMMITTED)
    version.mark_superseded()
    assert version.state == DocumentVersionState.SUPERSEDED


def test_done_alias_normalises_to_committed() -> None:
    version = DocumentVersion(state='done')
    assert version.state == DocumentVersionState.COMMITTED
