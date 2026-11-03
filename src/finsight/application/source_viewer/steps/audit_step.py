"""Deep module: source-view audit record step."""

from __future__ import annotations

from typing import Any

from finsight.application.source_viewer._step_helpers import _await, _coalesce, _get_attr
from finsight.application.source_viewer.step_result import StepResult

_AUDIT_METHOD_NAMES = (
    'append_source_view',
    'append',
    'record_source_view',
    'log_source_view',
    'write_source_view',
    'record_source_view_event',
    'emit',
    'append_event',
    'record',
    'write',
    'log',
    'create',
)

_STORAGE_ALIASES = (
    'audit_log',
    'audit',
    'audit_logger',
    'audit_log_port',
    'source_view_audit_log',
)


class AuditStep:
    """Best-effort audit write for a single source-view pipeline run."""

    def __init__(
        self,
        *,
        audit_log: Any = None,
        audit: Any = None,
        audit_logger: Any = None,
        audit_log_port: Any = None,
        source_view_audit_log: Any = None,
        **_aliases: Any,
    ) -> None:
        resolved = audit_log
        if resolved is None:
            resolved = audit
        if resolved is None:
            resolved = audit_logger
        if resolved is None:
            resolved = audit_log_port
        if resolved is None:
            resolved = source_view_audit_log
        if resolved is None:
            for key in _STORAGE_ALIASES:
                value = _aliases.get(key)
                if value is not None:
                    resolved = value
                    break
        self._audit_log = resolved

    def _context_value(self, context: Any, *attrs: str) -> Any:
        for attr in attrs:
            value = getattr(context, attr, None)
            if value is not None:
                return value
        extras = getattr(context, 'extras', None)
        if isinstance(extras, dict):
            for attr in attrs:
                value = extras.get(attr)
                if value is not None:
                    return value
        result_obj = getattr(context, 'result_obj', None)
        if result_obj is not None:
            for attr in attrs:
                value = getattr(result_obj, attr, None)
                if value is not None:
                    return value
        return None

    def _normalize_outcome(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(getattr(value, 'value', value)).strip().lower()
        if text in {'success', 'available', 'ok', 'completed', 'done', 'true'}:
            return 'success'
        if text in {
            'not_available',
            'not-available',
            'unavailable',
            'denied',
            'denial',
            'forbidden',
            'not allowed',
            'blocked',
        }:
            return 'not_available'
        if text in {'error', 'failure', 'failed', 'false'}:
            return 'error'
        return text or None

    def _outcome(self, context: Any) -> str:
        for attr in ('outcome', 'result', 'status'):
            normalized = self._normalize_outcome(getattr(context, attr, None))
            if normalized is not None:
                return normalized
        extras = getattr(context, 'extras', None)
        if isinstance(extras, dict):
            for key in ('outcome', 'result', 'status'):
                normalized = self._normalize_outcome(extras.get(key))
                if normalized is not None:
                    return normalized
        result_obj = getattr(context, 'result_obj', None)
        if result_obj is not None:
            for attr in ('outcome', 'result', 'status'):
                normalized = self._normalize_outcome(getattr(result_obj, attr, None))
                if normalized is not None:
                    return normalized
        return 'success'

    async def _run(self, context: Any) -> StepResult:
        audit = self._audit_log
        if audit is None:
            return StepResult.continue_(context)

        company_id = self._context_value(context, 'company_id', 'companyId', 'company', 'tenant_id')
        user_id = self._context_value(context, 'user_id', 'userId', 'user', 'actor', 'actor_id')
        role_raw = self._context_value(context, 'role')
        role = getattr(role_raw, 'value', role_raw)
        trace_id = self._context_value(context, 'trace_id', 'traceId', 'trace')
        locator = _coalesce(
            getattr(context, 'locator_token', None),
            getattr(context, 'citation_input', None),
            self._context_value(context, 'citation', 'locator', 'citation_locator'),
        )
        outcome = self._outcome(context)
        document_id = self._context_value(
            context, 'document_id', 'documentId', 'doc_id', 'docId', 'document'
        )
        version_id = self._context_value(
            context, 'version_id', 'versionId', 'version', 'document_version', 'document_version_id'
        )
        chunk_id = self._context_value(context, 'chunk_id', 'chunkId', 'chunk')
        if chunk_id is None:
            chunk_obj = getattr(context, 'chunk_obj', None)
            if chunk_obj is not None:
                chunk_id = _get_attr(chunk_obj, 'chunk_id', 'id', 'chunkId', default=None)
        page_raw = self._context_value(context, 'page', 'page_number', 'pageNumber', 'page_no')
        page = page_raw
        newer_available = getattr(context, 'newer_available', None)
        if newer_available is None:
            newer_available = getattr(context, 'newer_version_available', None)
        if newer_available is None:
            result_obj = getattr(context, 'result_obj', None)
            if result_obj is not None:
                newer_available = getattr(result_obj, 'newer_version_available', None)
        if newer_available is None:
            newer_available = bool(getattr(context, 'newer_id', None))
        needs_review = getattr(context, 'needs_review', None)
        if needs_review is None:
            result_obj = getattr(context, 'result_obj', None)
            if result_obj is not None:
                needs_review = getattr(result_obj, 'needs_review', None)
        if needs_review is None:
            needs_review = False

        method = None
        for name in _AUDIT_METHOD_NAMES:
            attr = getattr(audit, name, None)
            if callable(attr):
                method = attr
                break
        if method is None:
            return StepResult.continue_(context)

        event_kwargs = {
            'event_type': 'source_view',
            'action': 'source_view',
            'actor': user_id,
            'actor_id': user_id,
            'user_id': user_id,
            'user': user_id,
            'role': role,
            'company_id': company_id,
            'citation_locator': locator,
            'locator': locator,
            'citation': locator,
            'outcome': outcome,
            'status': outcome,
            'result': outcome,
            'trace_id': trace_id,
            'trace': trace_id,
            'resource_type': 'source_view',
            'details': {
                'document_id': document_id,
                'document_version': version_id,
                'version_id': version_id,
                'chunk_id': chunk_id,
                'page_number': page,
                'page': page,
                'newer_version_available': bool(newer_available)
                if newer_available is not None
                else False,
                'needs_review': bool(needs_review),
            },
            'metadata': {
                'document_id': document_id,
                'version_id': version_id,
                'page': page,
                'chunk_id': chunk_id,
                'newer_version_available': bool(newer_available)
                if newer_available is not None
                else False,
                'needs_review': bool(needs_review),
            },
            'document_id': document_id,
            'version_id': version_id,
            'document_version': version_id,
            'chunk_id': chunk_id,
            'page': page,
            'page_number': page,
            'newer_version_available': bool(newer_available)
            if newer_available is not None
            else False,
            'needs_review': bool(needs_review),
        }

        try:
            await _await(method(**event_kwargs))
        except TypeError:
            payload_without_company = {
                key: value for key, value in event_kwargs.items() if key != 'company_id'
            }
            try:
                await _await(method(company_id, **payload_without_company))
            except Exception:
                try:
                    await _await(method(**{'company_id': company_id, **payload_without_company}))
                except Exception:
                    pass
        except Exception:
            pass

        return StepResult.continue_(context)

    async def run(self, context: Any) -> StepResult:
        return await self._run(context)


__all__ = ['AuditStep']
