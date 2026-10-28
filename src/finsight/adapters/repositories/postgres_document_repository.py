"""Aurora/Postgres document repository implementing the DocumentRepository port.

Documents are versioned: a commit supersedes the previous committed version in
the same transaction while the old rows remain for audit. Deletes are soft for
``deleted_retention_days`` and can be restored from the recycle bin; a purge is
an explicit, privileged hard delete that still leaves audit rows alone.

Every statement carries ``company_id`` so queries prune to the tenant partition
and row-level security remains the second lock.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from finsight.domain.entities.document_version import DocumentVersion
from finsight.domain.ports.document_repository import DocumentRepository as DocumentRepositoryPort

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, DocumentId

_DOCUMENTS = 'documents'
_VERSIONS = 'document_versions'
_VERSION_COLUMNS = (
    'id, company_id, document_id, version, state, file_hash, filename, '
    'category, review_scope, created_at, updated_at'
)
_DOCUMENT_UPDATE_FIELDS = frozenset(
    {
        'filename',
        'content_type',
        'storage_key',
        'checksum_sha256',
        'document_type',
        'period_start',
        'period_end',
        'period',
        'status',
        'page_count',
        'category',
        'document_stamp',
    }
)
_VERSION_UPDATE_FIELDS = frozenset({'state', 'file_hash', 'filename', 'category', 'review_scope'})


class _Record(dict[str, Any]):
    """Row wrapper that supports attribute access in use cases."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_value(row: object | None, *names: str) -> object:
    if row is None:
        return None
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for name in names:
            try:
                if name in mapping:
                    return mapping[name]
            except TypeError:
                continue
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _row_to_record(row: object | None) -> _Record | None:
    if row is None:
        return None
    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        return _Record({str(key): mapping[key] for key in mapping})
    if isinstance(row, dict):
        return _Record(dict(row))
    return _Record({'value': row})


def _row_to_version(row: object | None) -> DocumentVersion | None:
    if row is None:
        return None
    return DocumentVersion(
        id=_row_value(row, 'id', 'version_id'),
        company_id=_row_value(row, 'company_id'),
        document_id=_row_value(row, 'document_id'),
        version=_row_value(row, 'version', 'version_number'),
        state=_row_value(row, 'state', 'status'),
        file_hash=_row_value(row, 'file_hash', 'content_hash'),
        filename=_row_value(row, 'filename', 'file_name'),
        category=_row_value(row, 'category', 'document_category'),
        review_scope=_row_value(row, 'review_scope', 'needs_review_scope'),
        created_at=_row_value(row, 'created_at'),
        updated_at=_row_value(row, 'updated_at'),
    )


def _rows_to_versions(rows: object) -> list[DocumentVersion]:
    versions: list[DocumentVersion] = []
    if not isinstance(rows, Iterable):
        return versions
    for row in rows:
        version = _row_to_version(row)
        if version is not None:
            versions.append(version)
    return versions


def _rows_to_records(rows: object) -> list[_Record]:
    records: list[_Record] = []
    if not isinstance(rows, Iterable):
        return records
    for row in rows:
        record = _row_to_record(row)
        if record is not None:
            records.append(record)
    return records


def _rowcount(result: object, fallback: int) -> int:
    rowcount = getattr(result, 'rowcount', None)
    if rowcount is None:
        return fallback
    try:
        return int(rowcount)
    except (TypeError, ValueError):
        return fallback


def _deleted(result: object) -> bool:
    rowcount = getattr(result, 'rowcount', None)
    if rowcount is None:
        return True
    try:
        return bool(int(rowcount))
    except (TypeError, ValueError):
        return True


def _version_values(
    company_id: str,
    document_version: DocumentVersion | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    source: dict[str, Any] = {}
    if document_version is not None:
        source = {
            'id': document_version.id,
            'company_id': document_version.company_id,
            'document_id': document_version.document_id,
            'version': document_version.version,
            'state': document_version.state,
            'file_hash': document_version.file_hash,
            'filename': document_version.filename,
            'category': document_version.category,
            'review_scope': document_version.review_scope,
        }
    source.update(kwargs)
    return {
        'id': _text(source.get('id') or source.get('version_id')) or str(uuid.uuid4()),
        'company_id': company_id,
        'document_id': _text(source.get('document_id')),
        'version': source.get('version') or source.get('version_number'),
        'state': _text(source.get('state') or source.get('status')) or 'received',
        'file_hash': _text(source.get('file_hash') or source.get('content_hash')),
        'filename': _text(source.get('filename') or source.get('file_name')),
        'category': _text(source.get('category') or source.get('document_category')),
        'review_scope': _text(source.get('review_scope')),
    }


class PostgresDocumentRepository(DocumentRepositoryPort, BaseRepository):
    """Document/version repository with supersession, soft delete and recycle bin.

    Without a session the adapter keeps records in memory for contract tests and
    the pilot composition path; a wired session always wins.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._documents: dict[str, dict[str, _Record]] = {}
        self._versions: dict[str, dict[str, _Record]] = {}

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def create_document(self, company_id: CompanyId, **kwargs: object) -> object:
        values = _document_values(str(company_id), kwargs)
        if self._session is None:
            self._documents.setdefault(str(company_id), {})[values['id']] = _Record(values)
            return _Record(values)
        await self._set_rls_context(company_id)
        columns = list(values)
        sql = (
            f'INSERT INTO {_DOCUMENTS} ({", ".join(columns)}) '
            f'VALUES ({", ".join(":" + column for column in columns)}) RETURNING *'
        )
        result = await self._execute(sql, values)
        return _row_to_record(await self._fetchone(result)) or _Record(values)

    async def get_document(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> object:
        include_deleted = bool(kwargs.get('include_deleted'))
        if self._session is None:
            record = self._documents.get(str(company_id), {}).get(str(document_id))
            if record is None or (record.get('deleted_at') and not include_deleted):
                return None
            return _Record(record)
        await self._set_rls_context(company_id)
        sql = f'SELECT * FROM {_DOCUMENTS} WHERE company_id = :company_id AND id = :id'
        if not include_deleted:
            sql += ' AND deleted_at IS NULL'
        result = await self._execute(sql, {'company_id': str(company_id), 'id': str(document_id)})
        return _row_to_record(await self._fetchone(result))

    async def update_document(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> object:
        values = {k: v for k, v in kwargs.items() if k in _DOCUMENT_UPDATE_FIELDS}
        if self._session is None:
            record = self._documents.get(str(company_id), {}).get(str(document_id))
            if record is None:
                return None
            record.update(values)
            record['updated_at'] = datetime.now(UTC)
            return _Record(record)
        await self._set_rls_context(company_id)
        assignments = [f'{column} = :{column}' for column in values]
        assignments.append('updated_at = now()')
        params: dict[str, Any] = {'company_id': str(company_id), 'id': str(document_id)}
        params.update(values)
        sql = (
            f'UPDATE {_DOCUMENTS} SET {", ".join(assignments)} '
            'WHERE company_id = :company_id AND id = :id RETURNING *'
        )
        result = await self._execute(sql, params)
        return _row_to_record(await self._fetchone(result))

    async def list_documents(self, company_id: CompanyId, **kwargs: object) -> list[object]:
        if self._session is None:
            return list(self._memory_documents(company_id, kwargs))
        await self._set_rls_context(company_id)
        where, params = _document_filters(str(company_id), kwargs)
        sql = f'SELECT * FROM {_DOCUMENTS} WHERE {" AND ".join(where)}'
        sql += _order_and_page(kwargs)
        result = await self._execute(sql, params)
        return list(_rows_to_records(await self._fetchall(result)))

    async def delete_document(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> bool:
        if kwargs.get('permanent') or kwargs.get('purge'):
            return await self.purge_document(company_id, document_id, **kwargs)
        return await self.soft_delete_document(company_id, document_id, **kwargs)

    async def soft_delete_document(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> bool:
        deleted_at = datetime.now(UTC)
        deleted_by = _text(kwargs.get('deleted_by') or kwargs.get('user_id'))
        reason = _text(kwargs.get('reason') or kwargs.get('deleted_reason'))
        if self._session is None:
            record = self._documents.get(str(company_id), {}).get(str(document_id))
            if record is None or record.get('deleted_at'):
                return False
            record.update(
                {
                    'deleted_at': deleted_at,
                    'deleted_by': deleted_by,
                    'deleted_reason': reason,
                    'status': 'deleted',
                    'updated_at': deleted_at,
                }
            )
            return True
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'UPDATE {_DOCUMENTS} SET deleted_at = now(), deleted_by = :deleted_by, '
            'deleted_reason = :reason, status = :status, updated_at = now() '
            'WHERE company_id = :company_id AND id = :id AND deleted_at IS NULL RETURNING id',
            {
                'company_id': str(company_id),
                'id': str(document_id),
                'deleted_by': deleted_by,
                'reason': reason,
                'status': 'deleted',
            },
        )
        return _deleted(result)

    async def restore_document(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> bool:
        retention_days = kwargs.get('retention_days') or kwargs.get('deleted_retention_days')
        if self._session is None:
            record = self._documents.get(str(company_id), {}).get(str(document_id))
            if record is None or not record.get('deleted_at'):
                return False
            if not _within_retention(record.get('deleted_at'), retention_days):
                return False
            record.update(
                {
                    'deleted_at': None,
                    'deleted_by': None,
                    'deleted_reason': None,
                    'status': kwargs.get('status') or 'committed',
                    'updated_at': datetime.now(UTC),
                }
            )
            return True
        await self._set_rls_context(company_id)
        sql = (
            f'UPDATE {_DOCUMENTS} SET deleted_at = NULL, deleted_by = NULL, '
            'deleted_reason = NULL, status = :status, updated_at = now() '
            'WHERE company_id = :company_id AND id = :id AND deleted_at IS NOT NULL'
        )
        params: dict[str, Any] = {
            'company_id': str(company_id),
            'id': str(document_id),
            'status': kwargs.get('status') or 'committed',
        }
        if retention_days is not None:
            sql += ' AND deleted_at >= now() - make_interval(days => :retention_days)'
            params['retention_days'] = int(str(retention_days))
        result = await self._execute(sql + ' RETURNING id', params)
        return _deleted(result)

    async def purge_document(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> bool:
        if self._session is None:
            documents = self._documents.get(str(company_id), {})
            if str(document_id) not in documents:
                return False
            del documents[str(document_id)]
            versions = self._versions.get(str(company_id), {})
            for version_id in [
                key
                for key, record in versions.items()
                if str(record.get('document_id')) == str(document_id)
            ]:
                del versions[version_id]
            return True
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_DOCUMENTS} WHERE company_id = :company_id AND id = :id RETURNING id',
            {'company_id': str(company_id), 'id': str(document_id)},
        )
        return _deleted(result)

    async def list_recycle_bin(self, company_id: CompanyId, **kwargs: object) -> list[object]:
        filters = dict(kwargs)
        filters['only_deleted'] = True
        filters['include_deleted'] = True
        return await self.list_documents(company_id, **filters)

    async def list_deleted_documents(self, company_id: CompanyId, **kwargs: object) -> list[object]:
        return await self.list_recycle_bin(company_id, **kwargs)

    async def purge_expired_documents(
        self,
        company_id: CompanyId,
        retention_days: int,
        **kwargs: object,
    ) -> int:
        cutoff = int(retention_days)
        if self._session is None:
            documents = self._documents.get(str(company_id), {})
            doomed = [
                document_id
                for document_id, record in documents.items()
                if record.get('deleted_at')
                and not _within_retention(record.get('deleted_at'), cutoff)
            ]
            for document_id in doomed:
                await self.purge_document(company_id, document_id)
            return len(doomed)
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_DOCUMENTS} WHERE company_id = :company_id '
            'AND deleted_at IS NOT NULL AND deleted_at < now() - make_interval(days => :days)',
            {'company_id': str(company_id), 'days': cutoff},
        )
        return _rowcount(result, 0)

    async def get_document_stamp(
        self,
        company_id: CompanyId,
        document_id: object,
        **kwargs: object,
    ) -> object:
        document = await self.get_document(company_id, document_id, **kwargs)
        if document is None:
            return None
        if isinstance(document, dict):
            return document.get('document_stamp')
        return getattr(document, 'document_stamp', None)

    async def update_document_stamp(
        self,
        company_id: CompanyId,
        document_id: object,
        stamp: object,
        **kwargs: object,
    ) -> object:
        value = getattr(stamp, 'value', stamp)
        return await self.update_document(
            company_id, document_id, document_stamp=str(value), **kwargs
        )

    # ------------------------------------------------------------------
    # Document versions
    # ------------------------------------------------------------------

    async def create_document_version(
        self,
        company_id: CompanyId,
        *,
        document_version: DocumentVersion | None = None,
        **kwargs: object,
    ) -> DocumentVersion:
        values = _version_values(str(company_id), document_version, dict(kwargs))
        if not values['document_id']:
            raise ValueError('document_id is required to create a document version')
        if self._session is None:
            return self._create_version_memory(values)
        await self._set_rls_context(company_id)
        if values['version'] is None:
            values['version'] = await self._next_version(company_id, values['document_id'])
        columns = list(values)
        sql = (
            f'INSERT INTO {_VERSIONS} ({", ".join(columns)}) '
            f'VALUES ({", ".join(":" + column for column in columns)}) RETURNING *'
        )
        result = await self._execute(sql, values)
        version = _row_to_version(await self._fetchone(result))
        if version is None:
            raise RuntimeError('document version insert returned no row')
        return version

    async def get_document_version(
        self,
        company_id: CompanyId,
        version_id: object,
        **kwargs: object,
    ) -> DocumentVersion | None:
        include_deleted = bool(kwargs.get('include_deleted'))
        if self._session is None:
            record = self._versions.get(str(company_id), {}).get(str(version_id))
            if record is None or record.get('deleted_at'):
                return None
            return _row_to_version(record)
        await self._set_rls_context(company_id)
        sql = f'SELECT v.* FROM {_VERSIONS} v WHERE v.company_id = :company_id AND v.id = :id'
        if not include_deleted:
            sql += (
                f' AND EXISTS (SELECT 1 FROM {_DOCUMENTS} d WHERE d.id = v.document_id '
                'AND d.company_id = v.company_id AND d.deleted_at IS NULL)'
            )
        result = await self._execute(sql, {'company_id': str(company_id), 'id': str(version_id)})
        return _row_to_version(await self._fetchone(result))

    async def update_document_version(
        self,
        company_id: CompanyId,
        version_id: object,
        **kwargs: object,
    ) -> DocumentVersion | None:
        values = {k: v for k, v in kwargs.items() if k in _VERSION_UPDATE_FIELDS}
        if self._session is None:
            record = self._versions.get(str(company_id), {}).get(str(version_id))
            if record is None:
                return None
            record.update(values)
            record['updated_at'] = datetime.now(UTC)
            return _row_to_version(record)
        await self._set_rls_context(company_id)
        assignments = [f'{column} = :{column}' for column in values]
        assignments.append('updated_at = now()')
        params: dict[str, Any] = {'company_id': str(company_id), 'id': str(version_id)}
        params.update(values)
        result = await self._execute(
            f'UPDATE {_VERSIONS} SET {", ".join(assignments)} '
            'WHERE company_id = :company_id AND id = :id RETURNING *',
            params,
        )
        return _row_to_version(await self._fetchone(result))

    async def list_document_versions(
        self,
        company_id: CompanyId,
        document_id: DocumentId | object | None = None,
        **kwargs: object,
    ) -> list[DocumentVersion]:
        if self._session is None:
            return self._list_versions_memory(company_id, document_id, kwargs)
        await self._set_rls_context(company_id)
        where, params = _version_filters(str(company_id), document_id, kwargs)
        sql = f'SELECT v.* FROM {_VERSIONS} v WHERE {" AND ".join(where)} ORDER BY v.version DESC'
        result = await self._execute(sql, params)
        return _rows_to_versions(await self._fetchall(result))

    async def get_latest_committed_version(
        self,
        company_id: CompanyId,
        document_id: DocumentId | object,
        **kwargs: object,
    ) -> DocumentVersion | None:
        versions = await self.list_document_versions(company_id, document_id, state='committed')
        return versions[0] if versions else None

    async def supersede_previous_versions(
        self,
        company_id: CompanyId,
        document_id: DocumentId | object,
        *,
        keep_version_id: object | None = None,
        **kwargs: object,
    ) -> int:
        keep = _text(keep_version_id)
        if self._session is None:
            changed = 0
            for record in self._versions.get(str(company_id), {}).values():
                if str(record.get('document_id')) != str(document_id):
                    continue
                if record.get('state') != 'committed':
                    continue
                if keep is not None and str(record.get('id')) == keep:
                    continue
                record['state'] = 'superseded'
                record['updated_at'] = datetime.now(UTC)
                changed += 1
            return changed
        await self._set_rls_context(company_id)
        sql = (
            f'UPDATE {_VERSIONS} SET state = :superseded, updated_at = now() '
            'WHERE company_id = :company_id AND document_id = :document_id '
            'AND state = :committed'
        )
        params: dict[str, Any] = {
            'company_id': str(company_id),
            'document_id': str(document_id),
            'superseded': 'superseded',
            'committed': 'committed',
        }
        if keep is not None:
            sql += ' AND id <> :keep_version_id'
            params['keep_version_id'] = keep
        result = await self._execute(sql, params)
        return _rowcount(result, 0)

    async def supersede_version(
        self,
        company_id: CompanyId,
        version_id: object,
        **kwargs: object,
    ) -> DocumentVersion | None:
        return await self.update_document_version(
            company_id, version_id, state='superseded', **kwargs
        )

    async def list_versions_for_audit(
        self,
        company_id: CompanyId,
        document_id: DocumentId | object | None = None,
        **kwargs: object,
    ) -> list[DocumentVersion]:
        filters = dict(kwargs)
        filters.setdefault('include_deleted', True)
        filters.setdefault('include_superseded', True)
        return await self.list_document_versions(company_id, document_id, **filters)

    async def document_version_markers(
        self, company_id: CompanyId, **kwargs: object
    ) -> dict[str, str]:
        """Return ``document_id -> marker`` for committed, non-deleted documents."""
        if self._session is None:
            markers: dict[str, str] = {}
            for document_id, record in self._documents.get(str(company_id), {}).items():
                if record.get('deleted_at'):
                    continue
                markers[document_id] = str(record.get('document_stamp') or '')
            return markers
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'SELECT id, document_stamp FROM {_DOCUMENTS} '
            'WHERE company_id = :company_id AND deleted_at IS NULL',
            {'company_id': str(company_id)},
        )
        markers = {}
        for record in _rows_to_records(await self._fetchall(result)):
            markers[str(record.get('id'))] = str(record.get('document_stamp') or '')
        return markers

    # ------------------------------------------------------------------
    # In-memory backend
    # ------------------------------------------------------------------

    def _memory_documents(self, company_id: CompanyId, kwargs: dict[str, object]) -> list[_Record]:
        include_deleted = bool(kwargs.get('include_deleted'))
        only_deleted = bool(kwargs.get('only_deleted'))
        category = _text(kwargs.get('category'))
        status = _text(kwargs.get('status'))
        records: list[_Record] = []
        for record in self._documents.get(str(company_id), {}).values():
            deleted = bool(record.get('deleted_at'))
            if deleted and not include_deleted:
                continue
            if only_deleted and not deleted:
                continue
            if category is not None and str(record.get('category')) != category:
                continue
            if status is not None and str(record.get('status')) != status:
                continue
            records.append(_Record(record))
        records.sort(key=lambda item: str(item.get('created_at') or ''), reverse=True)
        return records

    def _create_version_memory(self, values: dict[str, Any]) -> DocumentVersion:
        company_id = values['company_id']
        versions = self._versions.setdefault(company_id, {})
        if values['version'] is None:
            values['version'] = 1 + max(
                (
                    int(str(record.get('version') or 0))
                    for record in versions.values()
                    if str(record.get('document_id')) == values['document_id']
                ),
                default=0,
            )
        now = datetime.now(UTC)
        values.setdefault('created_at', now)
        values['updated_at'] = now
        record = _Record(values)
        versions[values['id']] = record
        version = _row_to_version(record)
        if version is None:
            raise RuntimeError('document version insert returned no row')
        return version

    def _list_versions_memory(
        self,
        company_id: CompanyId,
        document_id: DocumentId | object | None,
        kwargs: dict[str, object],
    ) -> list[DocumentVersion]:
        state = _text(kwargs.get('state'))
        include_superseded = bool(kwargs.get('include_superseded', True))
        include_deleted = bool(kwargs.get('include_deleted'))
        documents = self._documents.get(str(company_id), {})
        versions: list[DocumentVersion] = []
        for record in self._versions.get(str(company_id), {}).values():
            if document_id is not None and str(record.get('document_id')) != str(document_id):
                continue
            if not include_deleted:
                parent = documents.get(str(record.get('document_id')))
                if parent is not None and parent.get('deleted_at'):
                    continue
            if state is not None and str(record.get('state')) != state:
                continue
            if not include_superseded and record.get('state') == 'superseded':
                continue
            version = _row_to_version(record)
            if version is not None:
                versions.append(version)
        versions.sort(key=lambda item: int(str(item.version or 0)), reverse=True)
        return versions

    async def _next_version(self, company_id: CompanyId, document_id: object) -> int:
        result = await self._execute(
            f'SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM {_VERSIONS} '
            'WHERE company_id = :company_id AND document_id = :document_id',
            {'company_id': str(company_id), 'document_id': str(document_id)},
        )
        row = await self._fetchone(result)
        value = _row_value(row, 'next_version')
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return 1


def _document_values(company_id: str, kwargs: dict[str, object]) -> dict[str, Any]:
    values: dict[str, Any] = {
        'id': _text(kwargs.get('id') or kwargs.get('document_id')) or str(uuid.uuid4()),
        'company_id': company_id,
        'uploaded_by': _text(kwargs.get('uploaded_by') or kwargs.get('user_id')),
        'filename': _text(kwargs.get('filename') or kwargs.get('file_name')) or '',
        'content_type': _text(kwargs.get('content_type')),
        'storage_key': _text(kwargs.get('storage_key')) or '',
        'checksum_sha256': _text(kwargs.get('checksum_sha256') or kwargs.get('content_hash')),
        'document_type': _text(kwargs.get('document_type')),
        'period_start': kwargs.get('period_start'),
        'period_end': kwargs.get('period_end'),
        'period': _text(kwargs.get('period')),
        'category': _text(kwargs.get('category') or kwargs.get('document_category')),
        'status': _text(kwargs.get('status')) or 'received',
        'page_count': kwargs.get('page_count'),
        'document_stamp': _text(kwargs.get('document_stamp')),
    }
    return values


def _document_filters(
    company_id: str, kwargs: dict[str, object]
) -> tuple[list[str], dict[str, Any]]:
    where = ['company_id = :company_id']
    params: dict[str, Any] = {'company_id': company_id}
    if not kwargs.get('include_deleted'):
        where.append('deleted_at IS NULL')
    if kwargs.get('only_deleted'):
        where.append('deleted_at IS NOT NULL')
    for key in ('category', 'status', 'period'):
        value = _text(kwargs.get(key))
        if value is not None:
            where.append(f'{key} = :{key}')
            params[key] = value
    query = _text(kwargs.get('query') or kwargs.get('search') or kwargs.get('filename'))
    if query is not None:
        where.append('filename ILIKE :query')
        params['query'] = f'%{query}%'
    return where, params


def _version_filters(
    company_id: str,
    document_id: DocumentId | object | None,
    kwargs: dict[str, object],
) -> tuple[list[str], dict[str, Any]]:
    where = ['v.company_id = :company_id']
    params: dict[str, Any] = {'company_id': company_id}
    if document_id is not None:
        where.append('v.document_id = :document_id')
        params['document_id'] = str(document_id)
    state = _text(kwargs.get('state'))
    if state is not None:
        where.append('v.state = :state')
        params['state'] = state
    if not kwargs.get('include_superseded', True):
        where.append("v.state <> 'superseded'")
    if not kwargs.get('include_deleted'):
        where.append(
            f'EXISTS (SELECT 1 FROM {_DOCUMENTS} d WHERE d.id = v.document_id '
            'AND d.company_id = v.company_id AND d.deleted_at IS NULL)'
        )
    return where, params


def _order_and_page(kwargs: dict[str, object]) -> str:
    order_by = _text(kwargs.get('order_by')) or 'created_at'
    if not order_by or not str(order_by).replace('_', '').isalnum():
        order_by = 'created_at'
    direction = str(kwargs.get('direction') or 'DESC').upper()
    if direction not in {'ASC', 'DESC'}:
        direction = 'DESC'
    sql = f' ORDER BY {order_by} {direction}'
    limit = kwargs.get('limit') or kwargs.get('page_size')
    offset = kwargs.get('offset') or kwargs.get('skip')
    if limit is not None:
        sql += f' LIMIT {int(str(limit))}'
    if offset is not None:
        sql += f' OFFSET {int(str(offset))}'
    return sql


def _within_retention(deleted_at: object, retention_days: object) -> bool:
    if retention_days is None or not isinstance(deleted_at, datetime):
        return True
    if deleted_at.tzinfo is None:
        deleted_at = deleted_at.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - deleted_at).total_seconds() / 86_400
    return age_days <= int(str(retention_days))


AuroraDocumentRepository = PostgresDocumentRepository
PostgresDocumentRepo = PostgresDocumentRepository
DocumentRepositoryAdapter = PostgresDocumentRepository
RLSDocumentRepository = PostgresDocumentRepository
DocumentRepo = PostgresDocumentRepository

__all__ = [
    'AuroraDocumentRepository',
    'DocumentRepo',
    'DocumentRepositoryAdapter',
    'PostgresDocumentRepo',
    'PostgresDocumentRepository',
    'RLSDocumentRepository',
]
