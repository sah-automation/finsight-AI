"""Shared helpers for the chart endpoint (issue #380)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from finsight.domain.services.kpi_computation_service import KpiComputationService

_VERSION_ID_FIELDS = ('document_version_id', 'version_id', 'id')
_CATEGORY_FIELDS = ('category', 'document_category')
_STATE_FIELDS = ('state', 'status', 'document_status')
_TITLE_FIELDS = ('title', 'document_title')
_DOCUMENT_VERSION_FIELDS = ('version', 'document_version')
_CITATION_MIN_PARTS = 3


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
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


def _version_index(versions: Sequence[Any]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for version in versions:
        version_id = _text(_field(version, *_VERSION_ID_FIELDS))
        if version_id is None:
            continue
        index[version_id] = {
            'category': _text(_field(version, *_CATEGORY_FIELDS)) or '',
            'state': _text(_field(version, *_STATE_FIELDS)) or '',
            'title': _text(_field(version, *_TITLE_FIELDS)) or '',
            'version': _text(_field(version, *_DOCUMENT_VERSION_FIELDS)) or '',
        }
    return index


def _prepare_rows(
    rows: Sequence[dict[str, Any]],
    versions: Sequence[Any],
    breakdown_key: str | None,
    index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    statuses = {version_id: meta['state'] for version_id, meta in index.items() if meta['state']}
    prepared: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        category = index.get(_text(row.get('document_version_id')) or '', {}).get('category')
        if breakdown_key and category:
            enriched[breakdown_key] = category
        prepared.append(enriched)
    return KpiComputationService('chart').apply_display_labels(prepared, document_statuses=statuses)


def _source_documents(
    rows: Sequence[dict[str, Any]],
    versions: Sequence[Any],
    index: Mapping[str, dict[str, str]],
) -> list[dict[str, str]]:
    referenced: set[str] = set()
    for row in rows:
        version_id = _text(row.get('document_version_id'))
        if version_id:
            referenced.add(version_id)
        for citation in row.get('source_citations') or ():
            parts = str(citation).split(':')
            if str(citation).startswith('cit:v1:') and len(parts) >= _CITATION_MIN_PARTS:
                referenced.add(parts[2])
    documents: list[dict[str, str]] = []
    for version in versions:
        version_id = _text(_field(version, *_VERSION_ID_FIELDS))
        if version_id not in referenced:
            continue
        meta = index.get(version_id, {})
        if meta.get('title') or meta.get('version'):
            documents.append({'title': meta.get('title', ''), 'version': meta.get('version', '')})
    return documents


__all__ = [
    '_prepare_rows',
    '_source_documents',
    '_version_index',
]
