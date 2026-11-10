"""Pipeline behavior when a message references missing resources (issue #259).

A message whose document version is absent from the repository or whose S3
object is missing is a permanent failure: the pipeline must surface a specific
error type instead of a generic RuntimeError or a silently empty read, so the
worker can decide not to retry it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from finsight.application.ingest_document import pipeline_step_worker as m
from finsight.application.ingest_document.pipeline_step_worker import PipelineStepWorker
from finsight.core.errors import DocumentVersionNotFoundError, SourceObjectNotFoundError

if TYPE_CHECKING:
    from finsight.domain.value_objects.reader_result import ReaderResult

pytestmark = pytest.mark.unit

_REQUEST = {
    'company_id': 'company-a',
    'document_id': 'document-1',
    'version_id': 'version-1',
    'key': 'company-a/documents/document-1/versions/version-1/report.pdf',
}


class _MissingVersionRepository:
    """Document repository whose lookups never find the requested version."""

    async def get_document_version(self, company_id: Any, version_id: Any) -> Any:
        return None


class _RaisingObjectStorage:
    """Object storage port whose get_object raises the configured error."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def get_object(self, company_id: Any, key: Any, **kwargs: Any) -> bytes:
        raise self._error


class _StubReader:
    """Reader that must never run while the source object is unavailable."""

    async def read(self, company_id: Any, source: Any, **kwargs: Any) -> ReaderResult:
        raise AssertionError('reader must not run when the source object is missing')


class _NoSuchKeyError(Exception):
    """ClientError-shaped storage failure for a missing object."""

    response: ClassVar[dict[str, Any]] = {'Error': {'Code': 'NoSuchKey'}}

    def __str__(self) -> str:
        return 'An error occurred (NoSuchKey) when calling the GetObject operation'


class TestGetVersionMissing:
    async def test_raises_document_version_not_found_error(self) -> None:
        worker = PipelineStepWorker(
            step_name='read',
            document_repository=_MissingVersionRepository(),
            reader=_StubReader(),
        )

        with pytest.raises(DocumentVersionNotFoundError):
            await worker.handle(dict(_REQUEST))


class TestFetchSourceMissingObject:
    async def test_raises_source_object_not_found_for_no_such_key(self) -> None:
        worker = PipelineStepWorker(
            step_name='read',
            document_repository=None,
            reader=_StubReader(),
            object_storage=_RaisingObjectStorage(_NoSuchKeyError()),
        )

        with pytest.raises(SourceObjectNotFoundError):
            await worker.handle(dict(_REQUEST))

    async def test_raises_source_object_not_found_for_file_not_found(self) -> None:
        worker = PipelineStepWorker(
            step_name='read',
            document_repository=None,
            reader=_StubReader(),
            object_storage=_RaisingObjectStorage(FileNotFoundError('co/documents/doc/file.pdf')),
        )

        with pytest.raises(SourceObjectNotFoundError):
            await worker.handle(dict(_REQUEST))

    async def test_transient_storage_error_still_degrades_to_empty_read(self) -> None:
        worker = PipelineStepWorker(
            step_name='read',
            document_repository=None,
            reader=_StubReader(),
            object_storage=_RaisingObjectStorage(ConnectionError('socket reset')),
        )

        result = await worker.handle(dict(_REQUEST))

        assert isinstance(result, dict)
        assert result['status'] == 'processing'
        assert result['reader_result'].text == ''


class TestIsMissingObjectError:
    def test_botocore_shaped_client_error_code(self) -> None:
        assert m._is_missing_object_error(_NoSuchKeyError()) is True

    def test_error_code_attribute(self) -> None:
        class _CodedError(Exception):
            code = 'ObjectNotFound'

        assert m._is_missing_object_error(_CodedError('object gone')) is True

    def test_message_embedded_404(self) -> None:
        assert m._is_missing_object_error(Exception('An error occurred (404)')) is True

    def test_message_key_does_not_exist(self) -> None:
        assert m._is_missing_object_error(Exception('The specified key does not exist.')) is True

    def test_connection_error_is_not_missing_object(self) -> None:
        assert m._is_missing_object_error(ConnectionError('socket reset')) is False

    def test_unrelated_key_error_is_not_missing_object(self) -> None:
        assert m._is_missing_object_error(KeyError('unexpected')) is False
