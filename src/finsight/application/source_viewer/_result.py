"""Map a finished source-view context onto ``SourceViewerResult``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._step_helpers import _coalesce, _get_attr, _normalize_version_key, _text
from .models import SourceViewerResult

if TYPE_CHECKING:
    from .source_viewer_context import SourceViewerContext


def _cited_version_id(context: SourceViewerContext) -> Any:
    version_obj = context.version_obj
    if version_obj is None:
        return None
    try:
        return _normalize_version_key(version_obj)
    except Exception:  # noqa: BLE001
        return None


def _available_result(context: SourceViewerContext, initial: dict[str, Any]) -> SourceViewerResult:
    tables = context.tables if isinstance(context.tables, list) else list(context.tables or [])
    table_payload = context.table_payload
    if table_payload is None and tables:
        table_payload = tables[0]
    cited_id = _cited_version_id(context)
    locator = context.locator_token
    return SourceViewerResult(
        status='available',
        document_id=_coalesce(context.document_id, initial['document_id']),
        document_title=context.document_title,
        title=context.document_title,
        document_version=_coalesce(initial['version_id'], cited_id),
        version=_coalesce(initial['version_id'], cited_id),
        version_id=_coalesce(initial['version_id'], cited_id),
        page_number=_coalesce(context.page, initial['page']),
        page=_coalesce(context.page, initial['page']),
        content_type=_coalesce(context.content_type, 'text'),
        text=_text(context.text),
        table=table_payload,
        tables=tables,
        highlight=context.highlight,
        needs_review=bool(context.needs_review),
        newer_version_available=bool(context.newer_available),
        newer_version_id=context.newer_id,
        original_available=bool(context.original_available),
        original_link=_coalesce(context.signed_original_link, _get_attr(context, 'original_link')),
        citation=_coalesce(context.citation_input, initial['citation']),
        citation_locator=locator,
        locator=locator,
        company_id=_coalesce(context.company_id, initial['company_id']),
        user_id=context.user_id,
        role=context.role,
        trace_id=context.trace_id,
        outcome='success',
        result='available',
    )


def _stopped_result(
    context: SourceViewerContext, outcome: str, initial: dict[str, Any]
) -> SourceViewerResult:
    locator = context.locator_token
    return SourceViewerResult(
        status='not_available',
        document_id=initial['document_id'],
        document_title=None,
        page_number=initial['page'],
        content_type='text',
        text='',
        table=None,
        tables=[],
        highlight=None,
        needs_review=False,
        newer_version_available=False,
        newer_version_id=None,
        original_available=False,
        original_link=None,
        citation=_coalesce(context.citation_input, initial['citation']),
        citation_locator=locator,
        locator=locator,
        company_id=_coalesce(context.company_id, initial['company_id']),
        user_id=context.user_id,
        role=context.role,
        trace_id=context.trace_id,
        outcome='error' if outcome == 'error' else 'not_available',
        result='not_available',
    )


def build_source_viewer_result(
    context: SourceViewerContext, outcome: str, initial: dict[str, Any]
) -> SourceViewerResult:
    """Build the result value object and record it on the context."""
    if outcome == 'success':
        result = _available_result(context, initial)
    else:
        result = _stopped_result(context, outcome, initial)
    context.outcome = outcome
    context.result_obj = result
    return result


__all__ = ['build_source_viewer_result']
