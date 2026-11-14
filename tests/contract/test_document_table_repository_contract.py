"""Contract tests for the DocumentTableRepository port."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from finsight.adapters.repositories.postgres_document_table_repository import (
    PostgresDocumentTableRepository,
)
from finsight.core.types import CompanyId
from finsight.domain.entities.document_table import DocumentTable

if TYPE_CHECKING:
    from finsight.domain.ports import DocumentTableRepository

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


def _table(
    table_id: str,
    *,
    version_id: object = 'version-1',
    rows: list[list[object]] | None = None,
) -> DocumentTable:
    table_rows = rows if rows is not None else [['Revenue', 100]]
    return DocumentTable(
        company_id=COMPANY,
        document_id='document-a',
        version_id=version_id,
        page=1,
        index=0,
        table_id=table_id,
        payload={
            'table_id': table_id,
            'index': 0,
            'page': 1,
            'headers': ['Item', 'Total'],
            'rows': table_rows,
            'row_count': len(table_rows),
            'column_count': 2,
            'needs_review': False,
            'html': '<table></table>',
            'metadata': {},
        },
        html='<table></table>',
    )


@pytest.fixture
def repository() -> DocumentTableRepository:
    return PostgresDocumentTableRepository()


class TestDocumentTableRepositoryContract:
    async def test_upserts_are_keyed_by_company_version_and_table_id(
        self, repository: DocumentTableRepository
    ) -> None:
        await repository.upsert_document_tables(COMPANY, [_table('table-1')])
        await repository.upsert_document_tables(COMPANY, [_table('table-1', rows=[['Profit', 20]])])

        stored = await repository.list_document_tables(COMPANY, version_id='version-1')
        assert len(stored) == 1
        assert stored[0].table_id == 'table-1'
        assert stored[0].payload['rows'] == [['Profit', 20]]

    async def test_get_is_tenant_scoped_and_missing_rows_return_none(
        self, repository: DocumentTableRepository
    ) -> None:
        await repository.upsert_document_tables(COMPANY, [_table('table-1')])

        found = await repository.get_document_table(
            COMPANY, version_id='version-1', table_id='table-1'
        )
        missing = await repository.get_document_table(
            COMPANY, version_id='version-1', table_id='table-missing'
        )
        foreign = await repository.get_document_table(
            OTHER_COMPANY, version_id='version-1', table_id='table-1'
        )

        assert found is not None
        assert missing is None
        assert foreign is None

    async def test_upsert_rejects_a_table_from_another_tenant(
        self, repository: DocumentTableRepository
    ) -> None:
        foreign = DocumentTable(
            company_id=OTHER_COMPANY,
            document_id='document-a',
            version_id='version-1',
            table_id='table-1',
            payload={'table_id': 'table-1', 'rows': []},
        )

        with pytest.raises(ValueError):
            await repository.upsert_document_tables(COMPANY, [foreign])

    async def test_mark_version_inactive_accepts_uuid_version_ids(
        self, repository: DocumentTableRepository
    ) -> None:
        previous_version = uuid.uuid4()
        current_version = uuid.uuid4()
        await repository.upsert_document_tables(
            COMPANY,
            [
                _table('table-1', version_id=previous_version),
                _table('table-2', version_id=previous_version),
                _table('table-3', version_id=current_version),
            ],
        )

        changed = await repository.mark_version_document_tables_inactive(COMPANY, previous_version)

        assert changed == 2
        assert await repository.list_document_tables(COMPANY, version_id=previous_version) == []
        remaining = await repository.list_document_tables(COMPANY, version_id=current_version)
        assert [table.table_id for table in remaining] == ['table-3']

    async def test_superseded_rows_are_still_readable_for_history(
        self, repository: DocumentTableRepository
    ) -> None:
        await repository.upsert_document_tables(COMPANY, [_table('table-1')])
        await repository.mark_version_document_tables_inactive(COMPANY, 'version-1')

        history = await repository.list_document_tables(
            COMPANY, version_id='version-1', include_inactive=True
        )

        assert len(history) == 1
        assert history[0].is_active is False
