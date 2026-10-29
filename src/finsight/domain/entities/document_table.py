"""Domain entity for a persisted document table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from finsight.core.types import CompanyId, DocumentId


def _now() -> datetime:
    return datetime.now(UTC)


def _coalesce(*values: object, default: object = None) -> object:
    for value in values:
        if value is not None:
            return value
    return default


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if lowered in {'0', 'false', 'no', 'n', 'off'}:
            return False
    try:
        return bool(value)
    except (TypeError, ValueError):
        return default


class DocumentTable:
    """A normalised table extracted from a document version."""

    def __init__(self, *args: object, **kwargs: object) -> None:  # noqa: PLR0915
        positional = [
            'id',
            'company_id',
            'document_id',
            'version_id',
            'page',
            'index',
            'table_id',
            'payload',
            'html',
            'needs_review',
            'is_active',
        ]
        data: dict[str, object] = dict.fromkeys(positional)
        for index, value in enumerate(args):
            if index < len(positional):
                data[positional[index]] = value

        ident = _coalesce(
            data.get('id'),
            kwargs.get('id'),
            kwargs.get('document_table_id'),
            kwargs.get('document_table_row_id'),
            kwargs.get('row_id'),
            kwargs.get('uuid'),
            default=None,
        )

        company_id = _coalesce(
            data.get('company_id'),
            kwargs.get('company_id'),
            kwargs.get('companyId'),
            kwargs.get('tenant_id'),
            kwargs.get('tenant'),
            default=None,
        )
        document_id = _coalesce(
            data.get('document_id'),
            kwargs.get('document_id'),
            kwargs.get('documentId'),
            kwargs.get('doc_id'),
            kwargs.get('document'),
            default=None,
        )
        version_id = _coalesce(
            data.get('version_id'),
            kwargs.get('version_id'),
            kwargs.get('version'),
            kwargs.get('document_version'),
            kwargs.get('document_version_id'),
            kwargs.get('versionId'),
            default=None,
        )
        page = _coalesce(
            data.get('page'),
            kwargs.get('page'),
            kwargs.get('page_number'),
            kwargs.get('pageNumber'),
            kwargs.get('page_from'),
            kwargs.get('page_to'),
            default=None,
        )
        table_index = _coalesce(
            data.get('index'),
            kwargs.get('index'),
            kwargs.get('table_index'),
            kwargs.get('tableIndex'),
            kwargs.get('positional_index'),
            kwargs.get('position'),
            kwargs.get('ordinal'),
            kwargs.get('table_ordinal'),
            default=0,
        )
        table_id = _coalesce(
            data.get('table_id'),
            kwargs.get('table_id'),
            kwargs.get('tableId'),
            kwargs.get('table'),
            kwargs.get('table_name'),
            kwargs.get('name'),
            kwargs.get('title'),
            default=None,
        )
        payload = _coalesce(
            data.get('payload'),
            kwargs.get('payload'),
            kwargs.get('payload_json'),
            kwargs.get('payloadJson'),
            kwargs.get('data'),
            kwargs.get('table_data'),
            kwargs.get('rows'),
            kwargs.get('cells'),
            default=None,
        )
        html = _coalesce(
            data.get('html'),
            kwargs.get('html'),
            kwargs.get('html_text'),
            kwargs.get('htmlText'),
            kwargs.get('table_html'),
            kwargs.get('html_content'),
            default=None,
        )
        needs_review = _as_bool(
            _coalesce(
                data.get('needs_review'),
                kwargs.get('needs_review'),
                kwargs.get('needsReview'),
                default=False,
            ),
            default=False,
        )
        is_active = _as_bool(
            _coalesce(
                data.get('is_active'),
                kwargs.get('is_active'),
                kwargs.get('isActive'),
                default=True,
            ),
            default=True,
        )
        created_at = _coalesce(
            data.get('created_at') if 'created_at' in data else None,
            kwargs.get('created_at'),
            kwargs.get('createdAt'),
            default=None,
        )
        updated_at = _coalesce(
            kwargs.get('updated_at'),
            kwargs.get('updatedAt'),
            default=None,
        )

        if ident is None:
            ident = str(uuid.uuid4())
        if created_at is None:
            created_at = _now()
        if updated_at is None:
            updated_at = created_at

        self.id = ident
        self.document_table_id = ident
        self.table_row_id = ident
        self.row_id = ident
        self.company_id = None if company_id is None else CompanyId(str(company_id))
        self.document_id = None if document_id is None else DocumentId(str(document_id))
        self.document = self.document_id
        self.version_id = None if version_id is None else str(version_id)
        self.document_version = self.version_id
        self.document_version_id = self.version_id
        self.page = page
        self.page_number = page
        self.page_from = page
        self.index = int(str(table_index)) if table_index is not None else 0
        self.table_index = self.index
        self.ordinal = self.index
        self.positional_index = self.index
        self.position = self.index
        self.table_id = None if table_id is None else str(table_id)
        self.payload = payload
        self.payload_json = payload
        self.data = payload
        self.rows = payload
        self.html = html
        self.html_text = html
        self.table_html = html
        self.html_content = html
        self.needs_review = bool(needs_review)
        self.is_active = bool(is_active)
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def company(self) -> object:
        return self.company_id

    @classmethod
    def create(cls, **kwargs: object) -> DocumentTable:
        return cls(**kwargs)

    def mark_inactive(self) -> DocumentTable:
        self.is_active = False
        return self

    def mark_active(self) -> DocumentTable:
        self.is_active = True
        return self

    def __repr__(self) -> str:
        return f'DocumentTable(id={self.id!r}, table_id={self.table_id!r})'


__all__ = ['DocumentTable']
