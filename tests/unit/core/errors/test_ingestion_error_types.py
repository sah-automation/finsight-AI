"""Contract tests for permanent ingestion failure error types (issue #259)."""

from __future__ import annotations

import pytest

from finsight.core.errors import (
    DocumentError,
    DocumentVersionNotFoundError,
    FinSightError,
    SourceObjectNotFoundError,
)

pytestmark = pytest.mark.unit


class TestPermanentIngestionErrorTypes:
    def test_document_version_not_found_is_non_retryable_document_error(self) -> None:
        error = DocumentVersionNotFoundError('document version v1 missing')

        assert isinstance(error, DocumentError)
        assert isinstance(error, FinSightError)
        assert error.retryable is False
        assert error.code == 'DocumentVersionNotFoundError'

    def test_source_object_not_found_is_non_retryable_document_error(self) -> None:
        error = SourceObjectNotFoundError('source object k1 missing')

        assert isinstance(error, DocumentError)
        assert isinstance(error, FinSightError)
        assert error.retryable is False
        assert error.code == 'SourceObjectNotFoundError'
