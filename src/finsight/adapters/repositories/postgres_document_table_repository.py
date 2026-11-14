"""Aurora/Postgres document-table repository implementing the DocumentTableRepository port."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.document_table_repository import (
    DocumentTableRepository as DocumentTableRepositoryPort,
)

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.domain.entities.document_table import DocumentTable

    _TableList = list[DocumentTable]


class PostgresDocumentTableRepository(DocumentTableRepositoryPort, BaseRepository):
    """Document-table repository with in-memory support for contract tests."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, DocumentTable]] = {}

    async def __getattr__(self, name: str) -> Any:
        from ._postgres_document_table_repository_getattr import _getattr as helper

        return await helper(self, name)

    async def _get(self, company_id: Any, *args: Any, **kwargs: Any) -> DocumentTable | None:
        from ._postgres_document_table_repository__get import _get as helper

        return await helper(self, company_id, *args, **kwargs)

    async def _list(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository__list import _list as helper

        return await helper(self, company_id, *args, **kwargs)

    async def _mark_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository__mark_inactive import _mark_inactive as helper

        return await helper(self, company_id, *args, **kwargs)

    async def _upsert_many(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository__upsert_many import _upsert_many as helper

        return await helper(self, company_id, *args, **kwargs)

    async def deactivate(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_deactivate import _deactivate as helper

        return await helper(self, company_id, *args, **kwargs)

    async def find(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_find import _find as helper

        return await helper(self, company_id, *args, **kwargs)

    async def find_document_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_find_document_tables import (
            _find_document_tables as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def find_table(self, company_id: Any, *args: Any, **kwargs: Any) -> DocumentTable | None:
        from ._postgres_document_table_repository_find_table import _find_table as helper

        return await helper(self, company_id, *args, **kwargs)

    async def find_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_find_tables import _find_tables as helper

        return await helper(self, company_id, *args, **kwargs)

    async def get(self, company_id: Any, *args: Any, **kwargs: Any) -> DocumentTable | None:
        from ._postgres_document_table_repository_get import _get as helper

        return await helper(self, company_id, *args, **kwargs)

    async def get_document_table(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentTable | None:
        from ._postgres_document_table_repository_get_document_table import (
            _get_document_table as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def get_document_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_get_document_tables import (
            _get_document_tables as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def get_table(self, company_id: Any, *args: Any, **kwargs: Any) -> DocumentTable | None:
        from ._postgres_document_table_repository_get_table import _get_table as helper

        return await helper(self, company_id, *args, **kwargs)

    async def get_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_get_tables import _get_tables as helper

        return await helper(self, company_id, *args, **kwargs)

    async def list(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_list import _list as helper

        return await helper(self, company_id, *args, **kwargs)

    async def list_document_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_list_document_tables import (
            _list_document_tables as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def list_table(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_list_table import _list_table as helper

        return await helper(self, company_id, *args, **kwargs)

    async def list_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_list_tables import _list_tables as helper

        return await helper(self, company_id, *args, **kwargs)

    async def mark_document_table_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_mark_document_table_inactive import (
            _mark_document_table_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def mark_document_tables_inactive(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> int:
        from ._postgres_document_table_repository_mark_document_tables_inactive import (
            _mark_document_tables_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def mark_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_mark_inactive import _mark_inactive as helper

        return await helper(self, company_id, *args, **kwargs)

    async def mark_table_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_mark_table_inactive import (
            _mark_table_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def mark_tables_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_mark_tables_inactive import (
            _mark_tables_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def mark_version_document_tables_inactive(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> int:
        from ._postgres_document_table_repository_mark_version_document_tables_inactive import (
            _mark_version_document_tables_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def mark_version_table_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_mark_version_table_inactive import (
            _mark_version_table_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def mark_version_tables_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_table_repository_mark_version_tables_inactive import (
            _mark_version_tables_inactive as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def query(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_query import _query as helper

        return await helper(self, company_id, *args, **kwargs)

    async def query_document_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> _TableList:
        from ._postgres_document_table_repository_query_document_tables import (
            _query_document_tables as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def save(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_save import _save as helper

        return await helper(self, company_id, *args, **kwargs)

    async def save_document_table(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_save_document_table import (
            _save_document_table as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def save_document_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_save_document_tables import (
            _save_document_tables as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def save_table(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_save_table import _save_table as helper

        return await helper(self, company_id, *args, **kwargs)

    async def save_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_save_tables import _save_tables as helper

        return await helper(self, company_id, *args, **kwargs)

    async def upsert(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_upsert import _upsert as helper

        return await helper(self, company_id, *args, **kwargs)

    async def upsert_document_table(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentTable:
        from ._postgres_document_table_repository_upsert_document_table import (
            _upsert_document_table as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def upsert_document_tables(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> _TableList:
        from ._postgres_document_table_repository_upsert_document_tables import (
            _upsert_document_tables as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def upsert_table(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_upsert_table import _upsert_table as helper

        return await helper(self, company_id, *args, **kwargs)

    async def upsert_tables(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        from ._postgres_document_table_repository_upsert_tables import _upsert_tables as helper

        return await helper(self, company_id, *args, **kwargs)


# Compatibility aliases (preserved for external imports)
AuroraDocumentTableRepository = PostgresDocumentTableRepository
DocumentTableRepositoryAdapter = PostgresDocumentTableRepository
DocumentTablesRepository = PostgresDocumentTableRepository
PostgresDocumentTableRepo = PostgresDocumentTableRepository
PostgresDocumentTablesRepo = PostgresDocumentTableRepository
PostgresDocumentTablesRepository = PostgresDocumentTableRepository
RLSDocumentTableRepository = PostgresDocumentTableRepository
__all__ = [
    'AuroraDocumentTableRepository',
    'DocumentTableRepositoryAdapter',
    'DocumentTablesRepository',
    'PostgresDocumentTableRepo',
    'PostgresDocumentTableRepository',
    'PostgresDocumentTablesRepo',
    'PostgresDocumentTablesRepository',
    'RLSDocumentTableRepository',
]
