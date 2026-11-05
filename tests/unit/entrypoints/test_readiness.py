"""Readiness check reports which dependency is unavailable (#233)."""

# ruff: noqa: N803

from __future__ import annotations

from typing import Any

from finsight.entrypoints.api.readiness import build_readiness_report


class FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.executed: list[Any] = []

    def execute(self, statement: Any) -> Any:
        self.executed.append(statement)
        if self.fail:
            raise ConnectionError('database refused the connection')
        return object()


class FakeStorageClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.buckets: list[str] = []

    def head_bucket(self, *, Bucket: str) -> dict[str, Any]:
        self.buckets.append(Bucket)
        if self.fail:
            raise ConnectionError('object storage refused the connection')
        return {}


class FakeStorage:
    def __init__(self, *, fail: bool = False) -> None:
        self.bucket = 'test-documents'
        self._client = FakeStorageClient(fail=fail)

    def _get_client(self) -> FakeStorageClient:
        return self._client

    async def health_check(self) -> bool:
        return not self._client.fail


class FakeSqsClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def get_queue_attributes(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.fail:
            raise ConnectionError('queue refused the connection')
        return {'Attributes': {'QueueArn': 'arn:aws:sqs:local:000000000000:ingest'}}


class FakeQueue:
    def __init__(self, *, fail: bool = False) -> None:
        self.ingestion_queue_url = 'http://localhost:4566/000000000000/ingest'
        self._client = FakeSqsClient(fail=fail)
        self.fail = fail

    def _get_sqs_client(self) -> FakeSqsClient:
        return self._client

    async def health_check(self) -> bool:
        return not self.fail


class FakeContainer:
    def __init__(
        self,
        *,
        session: Any = None,
        storage: Any = None,
        queue: Any = None,
    ) -> None:
        self.session = session
        self.object_storage = storage
        self.queue = queue


async def test_all_dependencies_ready() -> None:
    container = FakeContainer(session=FakeSession(), storage=FakeStorage(), queue=FakeQueue())

    report = await build_readiness_report(container)

    assert report['ready'] is True
    assert report['failing'] == []
    assert all(check['status'] == 'ok' for check in report['checks'].values())


async def test_database_failure_is_named() -> None:
    session = FakeSession(fail=True)
    storage = FakeStorage()
    queue = FakeQueue()

    report = await build_readiness_report(
        FakeContainer(session=session, storage=storage, queue=queue)
    )

    assert report['ready'] is False
    assert report['failing'] == ['database']
    assert report['checks']['database']['status'] == 'unavailable'
    assert 'database' in report['checks']['database']['detail'].lower()
    # Other dependencies are still checked so operators see the full picture.
    assert report['checks']['object_storage']['status'] == 'ok'
    assert report['checks']['queue']['status'] == 'ok'


async def test_object_storage_failure_is_named() -> None:
    report = await build_readiness_report(
        FakeContainer(session=FakeSession(), storage=FakeStorage(fail=True), queue=FakeQueue())
    )

    assert report['ready'] is False
    assert report['failing'] == ['object_storage']
    assert report['checks']['object_storage']['status'] == 'unavailable'


async def test_queue_failure_is_named() -> None:
    report = await build_readiness_report(
        FakeContainer(session=FakeSession(), storage=FakeStorage(), queue=FakeQueue(fail=True))
    )

    assert report['ready'] is False
    assert report['failing'] == ['queue']
    assert report['checks']['queue']['status'] == 'unavailable'


async def test_missing_dependencies_are_all_named() -> None:
    report = await build_readiness_report(FakeContainer())

    assert report['ready'] is False
    assert report['failing'] == ['database', 'object_storage', 'queue']
    for check in report['checks'].values():
        assert check['status'] == 'unavailable'
        assert check['detail'] == 'not configured'
