"""Save-step tests for persisting normalised reader tables."""

from __future__ import annotations

from typing import Any

import pytest

from finsight.application.ingest_document import pipeline_step_worker as step_module
from finsight.application.ingest_document.save_worker import SaveWorker
from finsight.core.errors import DatabaseError
from finsight.core.types import CompanyId
from finsight.domain.value_objects.reader_result import ReaderResult

COMPANY = CompanyId('company-a')


class _TableRepository:
    def __init__(self) -> None:
        self.upserts: list[tuple[Any, Any]] = []
        self.inactive_versions: list[tuple[Any, Any]] = []
        self.returned: list[Any] | None = None

    async def upsert_document_tables(
        self, company_id: Any, tables: Any, **kwargs: Any
    ) -> list[Any]:
        self.upserts.append((company_id, tables))
        if self.returned is not None:
            return self.returned
        return list(tables)

    async def mark_version_document_tables_inactive(
        self, company_id: Any, version_id: Any, **kwargs: Any
    ) -> int:
        self.inactive_versions.append((company_id, version_id))
        return 1


class _FailingTableRepository(_TableRepository):
    async def upsert_document_tables(
        self, company_id: Any, tables: Any, **kwargs: Any
    ) -> list[Any]:
        raise RuntimeError('table store unavailable')


class _DocumentRepository:
    async def get_latest_committed_version(self, company_id: Any, document_id: Any) -> Any:
        return {'id': 'version-1'}

    async def supersede_previous_versions(
        self, company_id: Any, document_id: Any, keep_version_id: Any = None, **kwargs: Any
    ) -> None:
        return None

    async def update_document_stamp(self, company_id: Any, document_id: Any, stamp: Any) -> None:
        return None


def _seed(version_id: str, result: ReaderResult) -> None:
    step_module._IN_MEMORY_CHUNKS.clear()
    step_module._IN_MEMORY_CHUNKS[version_id] = {'reader_result': result, 'chunks': ['text']}


async def test_save_persists_normalised_tables_and_deactivates_previous_version() -> None:
    tables = _TableRepository()
    documents = _DocumentRepository()
    _seed(
        'version-2',
        ReaderResult(
            text='Revenue was 100.',
            tables=[
                {
                    'page_number': 4,
                    'table_id': 'table-9',
                    'index': 2,
                    'headers': ['Item', 'Total'],
                    'rows': [['Revenue', '100']],
                    'needs_review': True,
                }
            ],
        ),
    )
    worker = SaveWorker(
        document_repository=documents,
        document_table_repository=tables,
    )

    result = await worker._handle_request(
        company_id=COMPANY,
        version_id='version-2',
        document_id='document-a',
    )

    assert result['committed'] is True
    assert result['table_count'] == 1
    assert 'document_tables' not in result
    assert 'tables_persisted' not in result
    assert len(tables.upserts) == 1
    company_id, saved = tables.upserts[0]
    assert company_id == COMPANY
    assert len(saved) == 1
    assert saved[0].table_id == 'table-9'
    assert saved[0].version_id == 'version-2'
    assert saved[0].index == 0
    assert saved[0].payload['index'] == 0
    assert saved[0].payload['metadata']['reader_index'] == 2
    assert saved[0].payload['rows'] == [['Revenue', '100']]
    assert tables.inactive_versions == [(COMPANY, 'version-1')]


async def test_save_without_reader_tables_still_commits() -> None:
    tables = _TableRepository()
    documents = _DocumentRepository()
    _seed('version-2', ReaderResult(text='Text only.', tables=[]))
    worker = SaveWorker(
        document_repository=documents,
        document_table_repository=tables,
    )

    result = await worker._handle_request(
        company_id=COMPANY,
        version_id='version-2',
        document_id='document-a',
    )

    assert result['committed'] is True
    assert result['table_count'] == 0
    assert tables.upserts == []


async def test_save_fails_loudly_when_tables_exist_without_a_repository() -> None:
    documents = _DocumentRepository()
    _seed(
        'version-2',
        ReaderResult(text='Revenue was 100.', tables=[{'rows': [['Revenue', '100']]}]),
    )
    worker = SaveWorker(document_repository=documents)

    with pytest.raises(DatabaseError, match='document_table_repository'):
        await worker._handle_request(
            company_id=COMPANY,
            version_id='version-2',
            document_id='document-a',
        )


async def test_table_repository_failure_aborts_the_save_commit() -> None:
    tables = _FailingTableRepository()
    documents = _DocumentRepository()
    _seed(
        'version-2',
        ReaderResult(text='Revenue was 100.', tables=[{'rows': [['Revenue', '100']]}]),
    )
    worker = SaveWorker(
        document_repository=documents,
        document_table_repository=tables,
    )

    with pytest.raises(RuntimeError, match='table store unavailable'):
        await worker._handle_request(
            company_id=COMPANY,
            version_id='version-2',
            document_id='document-a',
        )


async def test_empty_repository_result_is_not_reported_as_persisted() -> None:
    tables = _TableRepository()
    tables.returned = []
    documents = _DocumentRepository()
    _seed(
        'version-2',
        ReaderResult(text='Revenue was 100.', tables=[{'rows': [['Revenue', '100']]}]),
    )
    worker = SaveWorker(
        document_repository=documents,
        document_table_repository=tables,
    )

    result = await worker._handle_request(
        company_id=COMPANY,
        version_id='version-2',
        document_id='document-a',
    )

    assert result['committed'] is True
    assert result['table_count'] == 0
