"""Tests that the new slice-4 adapters are wired through the composition root."""

from __future__ import annotations

from finsight.adapters.cache.answer_cache import AnswerCache
from finsight.adapters.messaging.change_event_publisher import ChangeEventPublisher
from finsight.adapters.repositories.postgres_chunk_repository import (
    PostgresChunkRepository,
)
from finsight.adapters.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from finsight.adapters.vector_store.aurora_pg_vector_write import AuroraPgVectorWrite
from finsight.composition import (
    build_answer_cache,
    build_change_event_publisher,
    build_chunk_repository,
    build_container,
    build_document_repository,
    build_vector_write,
)


def test_individual_builders_select_the_adapters() -> None:
    assert isinstance(build_chunk_repository(), PostgresChunkRepository)
    assert isinstance(build_document_repository(), PostgresDocumentRepository)
    assert isinstance(build_vector_write(), AuroraPgVectorWrite)
    assert isinstance(build_answer_cache(), AnswerCache)
    assert isinstance(build_change_event_publisher(), ChangeEventPublisher)


def test_container_exposes_the_same_adapter_instances() -> None:
    container = build_container()

    assert isinstance(container.chunk_repository, PostgresChunkRepository)
    assert isinstance(container.document_repository, PostgresDocumentRepository)
    assert isinstance(container.vector_write, AuroraPgVectorWrite)
    assert container.vector_store is container.vector_write
    assert isinstance(container.answer_cache, AnswerCache)
    assert isinstance(container.change_event_publisher, ChangeEventPublisher)
    assert container['chunk_repository'] is container.chunk_repository
    assert container['vector_write'] is container.vector_write
    assert container.repositories['chunk'] is container.chunk_repository
    assert container.adapters['change_event_publisher'] is container.change_event_publisher


def test_provided_dependencies_are_not_replaced() -> None:
    cache = AnswerCache(table_name='injected-cache')
    container = build_container(answer_cache=cache, change_event_publisher=ChangeEventPublisher())

    assert container.answer_cache is cache
    assert container.vector_write is not None


class _FakeTable:
    def put_item(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {}


class _FakeTransport:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []


def test_builders_forward_injected_session_table_and_transport() -> None:
    session = object()
    table = _FakeTable()
    transport = _FakeTransport()

    chunk_repository = build_chunk_repository(session=session)
    answer_cache = build_answer_cache(table=table, table_name='injected-cache')
    publisher = build_change_event_publisher(transport=transport)

    assert chunk_repository.session is session
    assert answer_cache.table is table
    assert answer_cache.table_name == 'injected-cache'
    assert publisher.transport is transport
