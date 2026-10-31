"""Shared helpers for PostgresDocumentRepository."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from finsight.domain.entities.document_version import DocumentVersion

if TYPE_CHECKING:
    from finsight.core.types import DocumentId

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
        extras={},
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
