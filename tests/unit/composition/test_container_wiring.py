"""Tests that the new slice-4 adapters are wired through the composition root."""

from __future__ import annotations

from typing import Any

from finsight.adapters.cache.answer_cache import AnswerCache
from finsight.adapters.messaging.change_event_publisher import ChangeEventPublisher
from finsight.adapters.repositories.postgres_chunk_repository import (
    PostgresChunkRepository,
)
from finsight.adapters.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from finsight.adapters.repositories.postgres_document_table_repository import (
    PostgresDocumentTableRepository,
)
from finsight.adapters.vector_store.aurora_pg_vector_write import AuroraPgVectorWrite
from finsight.composition import (
    build_answer_cache,
    build_change_event_publisher,
    build_chunk_repository,
    build_container,
    build_document_repository,
    build_document_table_repository,
    build_vector_write,
)
from finsight.core.config.loader import load_config


def test_individual_builders_select_the_adapters() -> None:
    assert isinstance(build_chunk_repository(), PostgresChunkRepository)
    assert isinstance(build_document_repository(), PostgresDocumentRepository)
    assert isinstance(build_document_table_repository(), PostgresDocumentTableRepository)
    assert isinstance(build_vector_write(), AuroraPgVectorWrite)
    assert isinstance(build_answer_cache(), AnswerCache)
    assert isinstance(build_change_event_publisher(), ChangeEventPublisher)


def test_container_exposes_the_same_adapter_instances() -> None:
    container = build_container(config=load_config('test'))

    assert isinstance(container.chunk_repository, PostgresChunkRepository)
    assert isinstance(container.document_repository, PostgresDocumentRepository)
    assert isinstance(container.document_table_repository, PostgresDocumentTableRepository)
    assert isinstance(container.vector_write, AuroraPgVectorWrite)
    assert container.vector_store is container.vector_write
    assert isinstance(container.answer_cache, AnswerCache)
    assert isinstance(container.change_event_publisher, ChangeEventPublisher)
    assert container['chunk_repository'] is container.chunk_repository
    assert container['document_table_repository'] is container.document_table_repository
    assert container['vector_write'] is container.vector_write
    assert container.repositories['chunk'] is container.chunk_repository
    assert container.repositories['document_table'] is container.document_table_repository
    assert container.adapters['change_event_publisher'] is container.change_event_publisher
    save_worker = container.step_functions_worker_set.get('save')
    assert save_worker is not None
    assert save_worker.document_table_repository is container.document_table_repository


def test_container_populates_the_fields_the_providers_read() -> None:
    """The providers resolve use cases from ``container.use_cases``."""
    container = build_container(config=load_config('test'))

    assert container.use_cases['ask'] is container.ask_question_use_case
    assert container.use_cases['upload'] is container.upload_use_case
    assert container.use_cases['onboarding'] is container.onboarding_use_case
    assert container.use_cases['source_viewer'] is container.source_viewer_use_case
    assert container.use_cases['documents'] is container.document_repository


def test_worker_set_alias_collapse_twenty_names_to_ten_instances() -> None:
    """Verify that the worker set maps 20 alias names to 10 unique step instances."""
    container = build_container(config=load_config('test'))
    worker_set = container.step_functions_worker_set

    # Primary step names (10 unique instances expected)
    primary_names = [
        'read',
        'delta',
        'chunk',
        'embed',
        'save',
        'cascade',
        'cache',
        'metric',
        'delta_tracking_check',
        'processing',
    ]

    # Aliases that should map to the same instances
    alias_groups = {
        'read': ['parse', 'extract'],
        'chunk': ['chunking', 'parse_chunks'],
        'embed': ['embedding'],
        'save': ['commit', 'persist', 'transaction', 'transactional', 'transactional_save'],
        'cascade': ['post_process', 'finalize', 'after_commit'],
        'cache': ['cache_clear', 'clear_cache', 'answer_cache'],
        'metric': ['metrics', 'extract_metrics', 'save_metrics'],
        'delta': [],
        'delta_tracking_check': [],
        'processing': [],
    }

    # Verify each primary name has a worker
    for name in primary_names:
        worker = worker_set.get(name)
        assert worker is not None, f'Missing worker for primary name: {name}'

    # Verify aliases map to the SAME instance (identity check)
    for primary, aliases in alias_groups.items():
        primary_worker = worker_set.get(primary)
        assert primary_worker is not None
        for alias in aliases:
            alias_worker = worker_set.get(alias)
            assert alias_worker is not None, f'Missing worker for alias: {alias}'
            assert alias_worker is primary_worker, (
                f'Alias {alias} does not share instance with {primary}: '
                f'{id(alias_worker)} != {id(primary_worker)}'
            )

    # Count unique instances among all 20 names
    all_names = primary_names + [a for aliases in alias_groups.values() for a in aliases]
    unique_instances = set()
    for name in all_names:
        worker = worker_set.get(name)
        if worker is not None:
            unique_instances.add(id(worker))

    # Should have exactly 10 unique instances (one per behavior)
    assert len(unique_instances) == 10, (
        f'Expected 10 unique step instances, got {len(unique_instances)}. '
        f'Names checked: {all_names}'
    )


def test_provided_dependencies_are_not_replaced() -> None:
    cache = AnswerCache(table_name='injected-cache')
    container = build_container(
        config=load_config('test'),
        answer_cache=cache,
        change_event_publisher=ChangeEventPublisher(),
    )

    assert container.answer_cache is cache
    assert container.vector_write is not None


class _FakeTable:
    def put_item(self, *args: Any, **kwargs: Any) -> dict[str, object]:
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
