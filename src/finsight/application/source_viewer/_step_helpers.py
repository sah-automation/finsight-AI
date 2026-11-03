"""Private helpers shared by the source-viewer pipeline steps.

Everything here is internal to the source-viewer package. The helpers only
read data from the context objects the steps receive and from domain ports.
They never read configuration or environment variables.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from typing import Any

from finsight.core.security.citation_locator import (
    decode_citation_locator,
    verify_citation_locator,
)

try:
    from finsight.domain.entities.document_version_state import DocumentVersionState
except ImportError:
    DocumentVersionState = None  # type: ignore[assignment,misc]


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if obj.get(name) is not None:
                return obj[name]
        elif obj is not None:
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _first(mapping: Any, *keys: str, default: Any = None) -> Any:
    return _get_attr(mapping, *keys, default=default)


def _text(value: Any) -> str:
    return '' if value is None else str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _normalize_state(value: Any) -> str:
    if value is None:
        return ''
    try:
        if DocumentVersionState is not None:
            return str(DocumentVersionState.normalize(value))
    except (TypeError, ValueError, AttributeError):
        pass
    return str(value).strip().lower()


def _normalize_version_key(value: Any) -> str | None:
    if value is None:
        return None
    ident = _get_attr(value, 'id', 'version_id', 'document_version_id')
    if ident is None:
        ident = value
    return str(ident)


def _allowed_contains(allowed: Any, action: str) -> bool:
    if isinstance(allowed, str):
        allowed = [allowed]
    if isinstance(allowed, (list, tuple, set)):
        values = [str(getattr(item, 'value', item)).lower() for item in allowed]
        return action.lower() in values or '*' in values
    return False


def decode_locator(token: str) -> Any:
    try:
        return decode_citation_locator(token)
    except (TypeError, ValueError):
        return {}


def verify_signed_locator(token: Any, secret: Any) -> bool:
    try:
        if secret is None:
            return bool(verify_citation_locator(token))
        return bool(verify_citation_locator(token, secret))
    except (TypeError, ValueError):
        return False


def _is_expired(created_at: Any, days: int) -> bool | None:
    if not isinstance(created_at, datetime):
        return None
    moment = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - moment > timedelta(days=days)


def _is_newer_version(cited: Any, candidate: Any) -> bool:
    cited_version = _get_attr(cited, 'version', 'version_number', 'revision')
    candidate_version = _get_attr(candidate, 'version', 'version_number', 'revision')
    try:
        if cited_version is not None and candidate_version is not None:
            if int(candidate_version) > int(cited_version):
                return True
            if int(candidate_version) < int(cited_version):
                return False
    except (TypeError, ValueError):
        pass
    cited_created = _get_attr(cited, 'created_at', 'updated_at')
    candidate_created = _get_attr(candidate, 'created_at', 'updated_at')
    if isinstance(cited_created, datetime) and isinstance(candidate_created, datetime):
        cited_moment = cited_created if cited_created.tzinfo else cited_created.replace(tzinfo=UTC)
        candidate_moment = (
            candidate_created if candidate_created.tzinfo else candidate_created.replace(tzinfo=UTC)
        )
        return candidate_moment > cited_moment
    return False


async def _call_document_get_version(repo: Any, company_id: Any, version_id: Any) -> Any:
    return await _await(repo.get_document_version(company_id, version_id))


async def _call_document_list_versions(repo: Any, company_id: Any, document_id: Any) -> Any:
    return await _await(repo.list_document_versions(company_id, document_id))


async def _call_document_latest_version(repo: Any, company_id: Any, document_id: Any) -> Any:
    method = getattr(repo, 'get_latest_committed_version', None)
    if not callable(method):
        return None
    return await _await(method(company_id, document_id))


async def _call_document_get(repo: Any, company_id: Any, document_id: Any) -> Any:
    return await _await(repo.get_document(company_id, document_id))


async def _call_chunk_get(repo: Any, company_id: Any, chunk_id: Any) -> Any:
    return await _await(repo.get_chunk(company_id, chunk_id))


async def _call_chunk_list(
    repo: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
) -> Any:
    _ = document_id, page
    return await _await(repo.list_chunks_by_version(company_id, version_id, include_inactive=False))


async def _call_table_list(
    repo: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
) -> list[Any]:
    rows = await _await(
        repo.list_document_tables(
            company_id, version_id=version_id, document_id=document_id, page_number=page
        )
    )
    return _as_list(rows)


async def _call_table_get(  # noqa: PLR0913, PLR0917
    repo: Any, company_id: Any, table_id: Any, version_id: Any, document_id: Any, page: Any
) -> Any:
    _ = version_id, document_id, page
    return await _await(repo.get_document_table(company_id, table_id))
