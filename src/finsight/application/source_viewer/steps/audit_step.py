"""Deep module: source-view audit record step."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import _await, _coalesce, _get_attr
from finsight.application.source_viewer.step_result import StepResult

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
    from finsight.domain.ports.audit_log import AuditLog

logger = logging.getLogger(__name__)

_SUCCESS = {'success', 'available', 'ok', 'completed', 'done', 'true', 'continue'}
_NOT_AVAILABLE = {
    'not_available',
    'not-available',
    'unavailable',
    'denied',
    'denial',
    'forbidden',
    'not allowed',
    'blocked',
}
_ERROR = {'error', 'failure', 'failed', 'false'}


class AuditStep:
    """Best-effort audit write for a single source-view pipeline run."""

    def __init__(self, *, audit_log: AuditLog | None = None) -> None:
        self._audit_log = audit_log

    def _normalize_outcome(self, value: Any) -> str | None:
        if value is None:
            return None
        value = getattr(value, 'kind', value)
        text = str(getattr(value, 'value', value)).strip().lower()
        if text in _SUCCESS:
            return 'success'
        if text in _NOT_AVAILABLE:
            return 'not_available'
        if text in _ERROR:
            return 'error'
        return text or None

    def _outcome(self, context: SourceViewerContext) -> str:
        for attr in ('outcome', 'result', 'status', 'kind'):
            normalized = self._normalize_outcome(_get_attr(context, attr))
            if normalized is not None:
                return normalized
        return 'success'

    async def _run_impl(self, context: SourceViewerContext) -> StepResult:
        audit = self._audit_log
        if audit is None:
            return StepResult.continue_(context)

        chunk_id = context.chunk_id
        if chunk_id is None and context.chunk_obj is not None:
            chunk_id = _get_attr(context.chunk_obj, 'chunk_id', 'id', 'chunkId')
        newer_available = context.newer_available
        if newer_available is None:
            newer_available = bool(context.newer_id)
        needs_review = context.needs_review if context.needs_review is not None else False
        details = {
            'document_id': context.document_id,
            'document_version': context.version_id,
            'version_id': context.version_id,
            'chunk_id': chunk_id,
            'page_number': context.page,
            'page': context.page,
            'newer_version_available': bool(newer_available),
            'needs_review': bool(needs_review),
        }
        role = getattr(context.role, 'value', context.role)
        locator = _coalesce(context.locator_token, context.citation_input)

        try:
            await _await(
                audit.append(
                    company_id=context.company_id,
                    event_type='source_view',
                    action='source_view',
                    actor=context.user_id,
                    user_id=context.user_id,
                    role=role,
                    citation_locator=locator,
                    outcome=self._outcome(context),
                    trace_id=context.trace_id,
                    resource_type='source_view',
                    details=details,
                    metadata=dict(details),
                )
            )
        except Exception:
            logger.debug('audit write failed (trace_id=%s)', context.trace_id, exc_info=True)
        return StepResult.continue_(context)

    async def run(self, context: SourceViewerContext) -> StepResult:
        try:
            return await self._run_impl(context)
        except Exception:
            logger.debug('audit step failed (trace_id=%s)', context.trace_id, exc_info=True)
            return StepResult.continue_(context)


__all__ = ['AuditStep']
