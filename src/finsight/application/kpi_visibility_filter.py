"""Filter KPI rows by the categories of their cited source documents."""

from __future__ import annotations

import binascii
from collections.abc import Mapping, Sequence
from typing import Any

from finsight.core.security.citation_locator import decode_citation_locator

_VERSION_ID_FIELDS = ('document_version_id', 'version_id', 'id')
_CATEGORY_FIELDS = ('category', 'document_category')
_CITATION_VERSION_INDEX = 2
_CITATION_MIN_PARTS = 3


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(getattr(value, 'value', value)).strip()
    return text or None


def _field(source: Any, *names: str) -> Any:
    if isinstance(source, Mapping):
        for name in names:
            if source.get(name) is not None:
                return source.get(name)
        return None
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _citation_version_id(citation: Any) -> str | None:
    text = _text(citation)
    if text is None:
        return None
    if text.startswith('cit:v1:'):
        parts = text.split(':')
        if len(parts) < _CITATION_MIN_PARTS:
            return None
        return _text(parts[_CITATION_VERSION_INDEX])
    if '.' in text:
        try:
            payload = decode_citation_locator(text)
        except (ValueError, TypeError, binascii.Error):
            return None
        return _text(payload.get('v'))
    return None


class KpiVisibilityFilter:
    """Remove KPI rows whose cited documents the caller may not read."""

    def __init__(
        self,
        *,
        category_permissions: Mapping[str, Sequence[Any]],
        access_scope: Sequence[Any] | None = None,
    ) -> None:
        self._category_permissions = category_permissions
        self._access_scope = (
            None if access_scope is None else {_text(item) for item in access_scope}
        )

    def filter(
        self,
        rows: Sequence[Mapping[str, Any]],
        document_versions: Sequence[Any],
    ) -> list[dict[str, Any]]:
        """Return a new list containing only rows with visible citations."""
        allowed = self._allowed_categories()
        categories = self._version_categories(document_versions)
        filtered: list[dict[str, Any]] = []
        for row in rows:
            visible = self._filter_row(row, categories, allowed)
            if visible is not None:
                filtered.append(visible)
        return filtered

    def _allowed_categories(self) -> set[str]:
        allowed: set[str] = set()
        for category, actions in self._category_permissions.items():
            category_id = _text(category)
            if category_id is None or 'read' not in {_text(action) for action in actions}:
                continue
            if self._access_scope is None or category_id in self._access_scope:
                allowed.add(category_id)
        return allowed

    def _version_categories(self, document_versions: Sequence[Any]) -> dict[str, str]:
        categories: dict[str, str] = {}
        for version in document_versions:
            category = _text(_field(version, *_CATEGORY_FIELDS))
            if category is None:
                continue
            for field_name in _VERSION_ID_FIELDS:
                version_id = _text(_field(version, field_name))
                if version_id is not None:
                    categories[version_id] = category
        return categories

    def _filter_row(
        self,
        row: Mapping[str, Any],
        categories: Mapping[str, str],
        allowed: set[str],
    ) -> dict[str, Any] | None:
        primary_version_id = _text(row.get('document_version_id'))
        if primary_version_id is None or categories.get(primary_version_id) not in allowed:
            return None
        citations = [
            (_citation_version_id(citation), citation)
            for citation in row.get('source_citations') or ()
        ]
        if any(
            version_id is not None and categories.get(version_id) not in allowed
            for version_id, _ in citations
        ):
            return None
        visible = dict(row)
        visible['source_citations'] = [
            citation
            for version_id, citation in citations
            if version_id is not None and categories.get(version_id) in allowed
        ]
        return visible
