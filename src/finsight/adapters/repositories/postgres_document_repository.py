"""Aurora/Postgres document repository implementing the DocumentRepository port.

Documents are versioned: a commit supersedes the previous committed version in
the same transaction while the old rows remain for audit. Deletes are soft for
``deleted_retention_days`` and can be restored from the recycle bin; a purge is
an explicit, privileged hard delete that still leaves audit rows alone.

Every statement carries ``company_id`` so queries prune to the tenant partition
and row-level security remains the second lock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.document_repository import DocumentRepository as DocumentRepositoryPort

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.domain.entities.document_version import DocumentVersion

    from ._postgres_document_repository_shared import _Record


class PostgresDocumentRepository(DocumentRepositoryPort, BaseRepository):
    """Document/version repository with supersession, soft delete and recycle bin.

    Without a session the adapter keeps records in memory for contract tests and
    the pilot composition path; a wired session always wins.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._documents: dict[str, dict[str, _Record]] = {}
        self._versions: dict[str, dict[str, _Record]] = {}

    def _create_version_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> DocumentVersion:
        from ._postgres_document_repository__create_version_memory import (
            _create_version_memory as helper,
        )

        return helper(self, company_id, *args, **kwargs)

    def _list_versions_memory(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> list[DocumentVersion]:
        from ._postgres_document_repository__list_versions_memory import (
            _list_versions_memory as helper,
        )

        return helper(self, company_id, *args, **kwargs)

    def _memory_documents(self, company_id: Any, *args: Any, **kwargs: Any) -> list[_Record]:
        from ._postgres_document_repository__memory_documents import _memory_documents as helper

        return helper(self, company_id, *args, **kwargs)

    async def _next_version(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_repository__next_version import _next_version as helper

        return await helper(self, company_id, *args, **kwargs)

    async def create_document(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._postgres_document_repository_create_document import _create_document as helper

        return await helper(self, company_id, *args, **kwargs)

    async def create_document_version(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentVersion:
        from ._postgres_document_repository_create_document_version import (
            _create_document_version as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def delete_document(self, company_id: Any, *args: Any, **kwargs: Any) -> bool:
        from ._postgres_document_repository_delete_document import _delete_document as helper

        return await helper(self, company_id, *args, **kwargs)

    async def document_version_markers(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> dict[str, str]:
        from ._postgres_document_repository_document_version_markers import (
            _document_version_markers as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def get_document(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._postgres_document_repository_get_document import _get_document as helper

        return await helper(self, company_id, *args, **kwargs)

    async def get_document_stamp(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._postgres_document_repository_get_document_stamp import _get_document_stamp as helper

        return await helper(self, company_id, *args, **kwargs)

    async def get_document_version(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentVersion | None:
        from ._postgres_document_repository_get_document_version import (
            _get_document_version as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def get_latest_committed_version(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentVersion | None:
        from ._postgres_document_repository_get_latest_committed_version import (
            _get_latest_committed_version as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def list_deleted_documents(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> list[object]:
        from ._postgres_document_repository_list_deleted_documents import (
            _list_deleted_documents as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def list_document_versions(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> list[DocumentVersion]:
        from ._postgres_document_repository_list_document_versions import (
            _list_document_versions as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def list_documents(self, company_id: Any, *args: Any, **kwargs: Any) -> list[object]:
        from ._postgres_document_repository_list_documents import _list_documents as helper

        return await helper(self, company_id, *args, **kwargs)

    async def list_recycle_bin(self, company_id: Any, *args: Any, **kwargs: Any) -> list[object]:
        from ._postgres_document_repository_list_recycle_bin import _list_recycle_bin as helper

        return await helper(self, company_id, *args, **kwargs)

    async def list_versions_for_audit(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> list[DocumentVersion]:
        from ._postgres_document_repository_list_versions_for_audit import (
            _list_versions_for_audit as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def purge_document(self, company_id: Any, *args: Any, **kwargs: Any) -> bool:
        from ._postgres_document_repository_purge_document import _purge_document as helper

        return await helper(self, company_id, *args, **kwargs)

    async def purge_expired_documents(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_repository_purge_expired_documents import (
            _purge_expired_documents as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def restore_document(self, company_id: Any, *args: Any, **kwargs: Any) -> bool:
        from ._postgres_document_repository_restore_document import _restore_document as helper

        return await helper(self, company_id, *args, **kwargs)

    async def soft_delete_document(self, company_id: Any, *args: Any, **kwargs: Any) -> bool:
        from ._postgres_document_repository_soft_delete_document import (
            _soft_delete_document as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def supersede_previous_versions(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._postgres_document_repository_supersede_previous_versions import (
            _supersede_previous_versions as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def supersede_version(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentVersion | None:
        from ._postgres_document_repository_supersede_version import _supersede_version as helper

        return await helper(self, company_id, *args, **kwargs)

    async def update_document(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._postgres_document_repository_update_document import _update_document as helper

        return await helper(self, company_id, *args, **kwargs)

    async def update_document_stamp(self, company_id: Any, *args: Any, **kwargs: Any) -> object:
        from ._postgres_document_repository_update_document_stamp import (
            _update_document_stamp as helper,
        )

        return await helper(self, company_id, *args, **kwargs)

    async def update_document_version(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> DocumentVersion | None:
        from ._postgres_document_repository_update_document_version import (
            _update_document_version as helper,
        )

        return await helper(self, company_id, *args, **kwargs)


# Compatibility aliases (preserved for external imports)
AuroraDocumentRepository = PostgresDocumentRepository
DocumentRepo = PostgresDocumentRepository
DocumentRepositoryAdapter = PostgresDocumentRepository
PostgresDocumentRepo = PostgresDocumentRepository
RLSDocumentRepository = PostgresDocumentRepository
__all__ = [
    'AuroraDocumentRepository',
    'DocumentRepo',
    'DocumentRepositoryAdapter',
    'PostgresDocumentRepo',
    'PostgresDocumentRepository',
    'RLSDocumentRepository',
]
