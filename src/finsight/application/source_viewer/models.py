# ruff: noqa: ANN401
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceViewerResult:
    status: str = 'available'
    document_id: Any = None
    document_title: Any = None
    title: Any = None
    document_version: Any = None
    version: Any = None
    version_id: Any = None
    page_number: Any = None
    page: Any = None
    content_type: str = 'text'
    text: str = ''
    table: Any = None
    tables: list[Any] = field(default_factory=list)
    highlight: Any = None
    needs_review: bool = False
    newer_version_available: bool = False
    newer_version_id: Any = None
    original_available: bool = False
    original_link: Any = None
    citation: Any = None
    locator: Any = None
    citation_locator: Any = None
    company_id: Any = None
    user_id: Any = None
    role: Any = None
    trace_id: Any = None
    outcome: str = 'success'
    result: str = 'available'

    def __post_init__(self) -> None:
        if self.title is None:
            self.title = self.document_title
        if self.document_title is None:
            self.document_title = self.title
        if self.version is None:
            self.version = self.document_version
        if self.document_version is None:
            self.document_version = self.version
        if self.version_id is None:
            self.version_id = self.document_version
        if self.page is None:
            self.page = self.page_number
        if self.page_number is None:
            self.page_number = self.page
        if self.locator is None:
            self.locator = self.citation_locator
        if self.citation_locator is None:
            self.citation_locator = self.locator
        if self.result == 'available' and self.status != 'available':
            self.result = self.status

    def __getitem__(self, key: str) -> Any:
        mapping = self.to_dict()
        if key not in mapping:
            raise KeyError(key)
        return mapping[key]

    def __contains__(self, key: object) -> bool:
        return key in self.to_dict()

    def keys(self) -> Any:
        return self.to_dict().keys()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'document_id': self.document_id,
            'document_title': self.document_title,
            'title': self.document_title,
            'document_version': self.document_version,
            'version': self.document_version,
            'version_id': self.document_version,
            'page_number': self.page_number,
            'page': self.page_number,
            'content_type': self.content_type,
            'text': self.text,
            'table': self.table,
            'tables': self.tables,
            'highlight': self.highlight,
            'needs_review': self.needs_review,
            'newer_version_available': self.newer_version_available,
            'newer_version_id': self.newer_version_id,
            'original_available': self.original_available,
            'original_link': self.original_link,
            'citation': self.citation,
            'citation_locator': self.citation_locator,
            'locator': self.citation_locator,
            'company_id': self.company_id,
            'user_id': self.user_id,
            'role': self.role,
            'trace_id': self.trace_id,
            'outcome': self.outcome,
            'result': self.result or self.status,
            'ok': self.status not in {'not_available', 'unavailable'},
            'available': self.status not in {'not_available', 'unavailable'},
        }


SourceViewResult = SourceViewerResult
ViewResult = SourceViewerResult
Result = SourceViewerResult

__all__ = ['Result', 'SourceViewResult', 'SourceViewerResult', 'ViewResult']
