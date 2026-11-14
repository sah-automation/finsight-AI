"""Helpers for :class:`EvidenceChecker`."""

from __future__ import annotations


def _coalesce(*names: str, kwargs: dict[str, object], default: object = None) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    return default


def _attr(obj: object, *names: str) -> object:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return None
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return None


def _to_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '')
    try:
        return float(text)
    except ValueError:
        return None


def is_citation_valid(citation: object) -> bool:
    """Return True when a citation points at a real, answer-time source."""
    if (
        not getattr(citation, 'document_id', '').strip()
        if hasattr(citation, 'document_id')
        else False
    ):
        return False
    document_id = getattr(citation, 'document_id', None)
    if document_id is None or not str(document_id).strip():
        return False
    version = getattr(citation, 'document_version', None)
    if version is None:
        version = getattr(citation, 'version', None)
    if version is None:
        version = getattr(citation, 'document_version_id', None)
    if version is None:
        version = getattr(citation, 'version_id', None)
    if version is None or not str(version).strip():
        # A citation must be pinned to the answer-time document version.
        return False
    page = getattr(citation, 'page_number', None)
    if page is not None:
        try:
            if int(page) < 1:
                return False
        except (TypeError, ValueError):
            return False
    return True


def answer_has_evidence(citations: object) -> bool:
    """Return True when an answer has at least one valid citation."""
    seq = citations if isinstance(citations, (list, tuple, set)) else [citations]
    if not seq:
        return False
    return all(c is not None and is_citation_valid(c) for c in seq)
