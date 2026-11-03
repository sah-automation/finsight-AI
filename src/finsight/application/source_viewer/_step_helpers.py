# ruff: noqa: ANN401, E501, BLE001, S110, PLC0415, TRY301, S112, B023, F841, SIM105, RET504, PLR0912, TRY300, RUF100, PLR0915, PLR0911, SIM103, SIM102, PLW0127, PLR0917, PLR0913, N818
from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from typing import Any


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif obj is not None and hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _first(mapping: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(mapping, dict):
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        elif mapping is not None and hasattr(mapping, key):
            value = getattr(mapping, key, None)
            if value is not None:
                return value
    return default


def _text(value: Any) -> str:
    return '' if value is None else str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _normalize_state(value: Any) -> str:
    if value is None:
        return ''
    try:
        from finsight.domain.entities.document_version_state import DocumentVersionState

        return str(DocumentVersionState.normalize(value))
    except Exception:
        return str(value).strip().lower()


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


def _normalize_version_key(value: Any) -> str | None:
    if value is None:
        return None
    ident = _get_attr(value, 'id', 'version_id', 'document_version_id', default=None)
    if ident is None and not isinstance(value, dict):
        ident = getattr(
            value, 'id', getattr(value, 'version_id', getattr(value, 'document_version_id', None))
        )
    if ident is None and isinstance(value, dict):
        ident = value.get('id', value.get('version_id', value.get('document_version_id')))
    if ident is None:
        ident = value
    return None if ident is None else str(ident)


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is not None and (
            hasattr(arg, 'switches') or hasattr(arg, 'documents') or hasattr(arg, 'app')
        ):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None and (
            hasattr(value, 'switches') or hasattr(value, 'documents') or isinstance(value, dict)
        ):
            return value
    for key in ('container', 'composition', 'root', 'app', 'use_case'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return kwargs.get('llm_config') or kwargs.get('model_config')


def _looks_config(value: Any) -> bool:
    return hasattr(value, 'switches') or hasattr(value, 'documents') or hasattr(value, 'app')


def _looks_audit(value: Any) -> bool:
    for name in ('append', 'append_source_view', 'record', 'emit', 'write'):
        if hasattr(value, name) and callable(getattr(value, name)):
            return True
    return False


def _looks_chunk_repo(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in ('get_chunk', 'list_chunks_by_version', 'list_chunks_by_document')
    )


def _looks_table_repo(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in (
            'list_document_tables',
            'list_tables',
            'upsert_document_tables',
            'get_document_table',
        )
    )


def _looks_document_repo(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in ('get_document_version', 'list_document_versions', 'get_version', 'list_versions')
    )


def _looks_storage(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in (
            'generate_presigned_download_url',
            'generate_presigned_download',
            'presigned_download_url',
            'download_url',
            '_normalize_key',
            'build_key',
        )
    )


def _looks_context(value: Any) -> bool:
    if isinstance(value, dict):
        return any(k in value for k in ('company_id', 'role', 'permissions', 'access_scope'))
    return hasattr(value, 'company_id') and (
        hasattr(value, 'role') or hasattr(value, 'permissions')
    )


def _looks_request(value: Any) -> bool:
    return isinstance(value, dict) or any(
        hasattr(value, n) for n in ('document_id', 'citation', 'citation_locator', 'company_id')
    )


def _allowed_contains(allowed: Any, action: str) -> bool:
    if isinstance(allowed, str):
        allowed = [allowed]
    if isinstance(allowed, (list, tuple, set)):
        vals = [str(getattr(x, 'value', x)).lower() for x in allowed]
        return action.lower() in vals or '*' in vals
    return False


def _load_permission_matrix(config: Any) -> Any:
    if config is None:
        return None
    perms = getattr(config, 'permissions', None)
    if perms is not None:
        if hasattr(perms, 'model_dump'):
            try:
                return perms.model_dump()
            except Exception:
                pass
        if isinstance(perms, dict):
            return perms
    # try yaml file via config access path
    try:
        from pathlib import Path

        import yaml

        candidates = ['config/permissions.yaml', 'permissions.yaml']
        for cand in candidates:
            p = Path(cand)
            if p.exists():
                return yaml.safe_load(p.read_text())
    except Exception:
        pass
    return None


def list_documents_category() -> list[Any]:
    try:
        from finsight.core.types import DocumentCategory

        return list(DocumentCategory)
    except Exception:
        return []


def decode_locator(token: str) -> Any:
    try:
        from finsight.core.security.citation_locator import decode_citation_locator

        return decode_citation_locator(token)
    except Exception:
        try:
            from finsight.core.security.citation_locator import decode_citation_locator as dcl

            return dcl(token)
        except Exception:
            return {}


def verify_signed_locator(token: Any, secret: Any) -> bool:
    try:
        from finsight.core.security.citation_locator import verify_citation_locator

        if secret is None:
            return verify_citation_locator(token)  # type: ignore[no-any-return]
        return verify_citation_locator(token, secret)  # type: ignore[no-any-return]
    except Exception:
        return False


def _is_expired(created_at: Any, days: int) -> bool | None:
    if created_at is None:
        return None
    try:
        if isinstance(created_at, (datetime,)):
            dt = created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return datetime.now(UTC) - dt > timedelta(days=days)
    except Exception:
        pass
    return None


def _is_newer_version(cited: Any, candidate: Any) -> bool:
    # compare version numbers first
    cited_ver = _get_attr(cited, 'version', 'version_number', 'revision')
    cand_ver = _get_attr(candidate, 'version', 'version_number', 'revision')
    try:
        if cited_ver is not None and cand_ver is not None:
            if int(cand_ver) > int(cited_ver):
                return True
            if int(cand_ver) < int(cited_ver):
                return False
    except (TypeError, ValueError):
        try:
            if float(cand_ver) > float(cited_ver):
                return True
        except Exception:
            pass
    # fall back to created_at
    cited_created = _get_attr(cited, 'created_at', 'updated_at')
    cand_created = _get_attr(candidate, 'created_at', 'updated_at')
    if isinstance(cited_created, datetime) and isinstance(cand_created, datetime):
        a = cited_created if cited_created.tzinfo else cited_created.replace(tzinfo=UTC)
        b = cand_created if cand_created.tzinfo else cand_created.replace(tzinfo=UTC)
        return b > a
    return False


# ---------- repository call helpers ----------


async def _call_document_get_version(repo: Any, company_id: Any, version_id: Any) -> Any:
    for name in (
        'get_document_version',
        'get_version',
        'get_document_version_by_id',
        'get_version_by_id',
    ):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(meth(company_id, version_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, version_id=version_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_document_list_versions(repo: Any, company_id: Any, document_id: Any) -> Any:
    for name in (
        'list_document_versions',
        'list_versions',
        'find_versions',
        'list_versions_by_document',
    ):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                if document_id is not None:
                    return await _await(meth(company_id, document_id))
                return await _await(meth(company_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, document_id=document_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_document_latest_version(repo: Any, company_id: Any, document_id: Any) -> Any:
    for name in ('get_latest_committed_version', 'latest_committed_version', 'get_latest_version'):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                if document_id is not None:
                    return await _await(meth(company_id, document_id))
                return await _await(meth(company_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, document_id=document_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_document_get(repo: Any, company_id: Any, document_id: Any) -> Any:
    for name in ('get_document', 'get'):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(meth(company_id, document_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, document_id=document_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_chunk_get(repo: Any, company_id: Any, chunk_id: Any) -> Any:
    for name in ('get_chunk', 'get'):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(meth(company_id, chunk_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, chunk_id=chunk_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_chunk_list(
    repo: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
) -> Any:
    for name in ('list_chunks_by_version', 'list_chunks', 'list_by_version', 'chunks_by_version'):
        meth = getattr(repo, name, None)
        if callable(meth):
            # version_id filters
            try:
                res = await _await(meth(company_id, version_id, include_inactive=False))
                return res
            except TypeError:
                try:
                    res = await _await(
                        meth(company_id=company_id, version_id=version_id, include_inactive=False)
                    )
                    return res
                except TypeError:
                    continue
                except Exception:
                    raise
    for name in ('list_chunks_by_document',):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(
                    meth(company_id, document_id, version_id=version_id, include_inactive=False)
                )
            except Exception:
                continue
    return []


async def _call_table_list(
    repo: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
) -> list[Any]:
    methods = ('list_document_tables', 'list_tables', 'list', 'get_tables')
    for name in methods:
        meth = getattr(repo, name, None)
        if callable(meth):
            # Try many call styles
            attempts = [
                lambda: meth(
                    company_id, version_id=version_id, document_id=document_id, page_number=page
                ),
                lambda: meth(company_id, version_id, document_id=document_id, page_number=page),
                lambda: meth(company_id, version_id),
                lambda: meth(company_id, document_id=document_id, version_id=version_id),
                lambda: meth(company_id),
            ]
            for attempt in attempts:
                try:
                    res = await _await(attempt())  # type: ignore[no-untyped-call]
                    if res is None:
                        continue
                    return _as_list(res)
                except TypeError:
                    continue
                except Exception:
                    raise
    return []


async def _call_table_get(
    repo: Any, company_id: Any, table_id: Any, version_id: Any, document_id: Any, page: Any
) -> Any:
    methods = ('get_document_table', 'get_table', 'get')
    for name in methods:
        meth = getattr(repo, name, None)
        if callable(meth):
            attempts = [
                lambda: meth(company_id, table_id),
                lambda: meth(company_id, table_id=table_id),
                lambda: meth(
                    company_id, version_id=version_id, table_id=table_id, document_id=document_id
                ),
            ]
            for attempt in attempts:
                try:
                    res = await _await(attempt())  # type: ignore[no-untyped-call]
                    if res is not None:
                        return res
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


def _looks_table_id(value: Any) -> bool:
    text = str(value or '').lower()
    return 'table' in text


def _table_to_payload(table: Any) -> Any:
    if table is None:
        return None
    table_id = _get_attr(table, 'table_id', 'id', 'table')
    payload = _get_attr(table, 'payload', 'data', 'payload_json')
    if payload is None:
        payload = getattr(table, 'payload', None)
    html = _get_attr(table, 'html', 'html_text', 'table_html', 'html_content')
    needs_review = bool(_get_attr(table, 'needs_review'))
    page = _get_attr(table, 'page', 'page_number')
    index = _get_attr(table, 'index', 'table_index', default=0)
    result = {
        'table_id': None if table_id is None else str(table_id),
        'id': None if table_id is None else str(table_id),
        'payload': payload,
        'data': payload,
        'structured': payload,
        'json': payload,
        'html': html,
        'html_text': html,
        'table_html': html,
        'needs_review': needs_review,
        'page': page,
        'page_number': page,
        'index': index,
    }
    return result


def _table_text(table_payload: Any) -> str:
    if not isinstance(table_payload, dict):
        return ''
    payload = table_payload.get('payload')
    if isinstance(payload, dict):
        rows = payload.get('rows')
        if isinstance(rows, list):
            lines = []
            for row in rows:
                if isinstance(row, (list, tuple)):
                    lines.append(' | '.join(str(x) for x in row))
                else:
                    lines.append(str(row))
            return '\n'.join(lines)
    return ''


__all__ = [
    '_allowed_contains',
    '_as_int',
    '_as_list',
    '_await',
    '_call_chunk_get',
    '_call_chunk_list',
    '_call_document_get',
    '_call_document_get_version',
    '_call_document_latest_version',
    '_call_document_list_versions',
    '_call_table_get',
    '_call_table_list',
    '_coalesce',
    '_first',
    '_get_attr',
    '_is_expired',
    '_is_newer_version',
    '_load_permission_matrix',
    '_looks_audit',
    '_looks_chunk_repo',
    '_looks_config',
    '_looks_context',
    '_looks_document_repo',
    '_looks_request',
    '_looks_storage',
    '_looks_table_id',
    '_looks_table_repo',
    '_normalize_state',
    '_normalize_version_key',
    '_resolve_config',
    '_table_text',
    '_table_to_payload',
    '_text',
    'decode_locator',
    'list_documents_category',
    'verify_signed_locator',
]
