"""Deep module: citation resolution (signed locator verification) step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import (
    _as_int,
    _first,
    _get_attr,
)
from finsight.application.source_viewer._step_helpers import (
    decode_locator as _decode_locator_helper,
)
from finsight.application.source_viewer._step_helpers import (
    verify_signed_locator as _verify_signed_locator_helper,
)
from finsight.application.source_viewer.step_result import StepResult

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import (  # noqa: TC001
        SourceViewerContext,
    )


class ResolveCitationStep:
    """Verify the caller's citation input and decode locator claims.

    The signing key is injected (resolved from configuration by the composition
    root). No config or environment access happens here.
    """

    def __init__(self, *, signing_key: str) -> None:
        if not signing_key:
            raise ValueError('signing_key must be configured')
        self._signing_key = signing_key

    def _citation_input(self, context: Any) -> Any:
        return _get_attr(context, 'citation_input', 'citation', 'citation_locator', 'locator')

    def _set_if_none(self, context: Any, attr: str, value: Any) -> None:
        if value is not None and getattr(context, attr, None) is None:
            setattr(context, attr, value)

    def _decode(self, token: Any) -> Any:
        try:
            decoded = _decode_locator_helper(token)
        except Exception:
            return None
        if not isinstance(decoded, dict) or not decoded:
            return None
        return decoded

    def _apply_object_fields(self, context: Any, citation: Any) -> None:
        self._set_if_none(
            context,
            'document_id',
            _first(citation, 'document_id', 'documentId', 'doc_id', 'document'),
        )
        self._set_if_none(
            context,
            'version_id',
            _first(
                citation,
                'document_version',
                'document_version_id',
                'version',
                'version_id',
            ),
        )
        self._set_if_none(
            context,
            'chunk_id',
            _first(citation, 'chunk_id', 'chunkId', 'chunk', 'table_id', 'tableId', 'table'),
        )

        _page = _first(citation, 'page_number', 'pageNumber', 'page')
        _page_value = _as_int(_page)
        self._set_if_none(
            context,
            'page',
            _page_value if _page_value is not None else _page,
        )

        self._set_if_none(
            context,
            'category',
            _first(citation, 'document_category', 'documentCategory', 'category'),
        )

    def _apply_locator(self, context: Any, token: Any, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        self._set_if_none(context, 'document_id', payload.get('d'))
        self._set_if_none(context, 'version_id', payload.get('v'))
        self._set_if_none(context, 'chunk_id', payload.get('c'))
        _loc_page = payload.get('p')
        _loc_page_value = _as_int(_loc_page)
        self._set_if_none(
            context,
            'page',
            _loc_page_value if _loc_page_value is not None else _loc_page,
        )
        if getattr(context, 'highlight', None) is None:
            start = _as_int(payload.get('s'))
            end = _as_int(payload.get('e'))
            if start is not None or end is not None:
                context.highlight = {
                    'start_char': start,
                    'end_char': end,
                    'char_start': start,
                    'char_end': end,
                    'start': start,
                    'end': end,
                    's': start,
                    'e': end,
                }
        self._set_if_none(context, 'locator_token', token)
        self._set_if_none(context, 'locator', token)
        self._set_if_none(context, 'locator_payload', payload)

    async def run(self, context: SourceViewerContext) -> StepResult:
        """Verify the citation input and decode locator claims onto ``context``."""
        citation_input = self._citation_input(context)
        if citation_input is None:
            return StepResult.continue_(context)
        if isinstance(citation_input, str):
            if '.' not in citation_input:
                return StepResult.continue_(context)
            if not _verify_signed_locator_helper(citation_input, self._signing_key):
                return StepResult.stop_with_not_available(context)
            payload = self._decode(citation_input)
            if not isinstance(payload, dict):
                return StepResult.stop_with_not_available(context)
            self._apply_locator(context, citation_input, payload)
            return StepResult.continue_(context)
        locator_token = _first(
            citation_input, 'citation_locator', 'locator', 'token', 'citation_id', 'id'
        )
        payload = None
        if isinstance(locator_token, str):
            if not _verify_signed_locator_helper(locator_token, self._signing_key):
                return StepResult.stop_with_not_available(context)
            payload = self._decode(locator_token)
            if not isinstance(payload, dict):
                return StepResult.stop_with_not_available(context)
        self._apply_object_fields(context, citation_input)
        if isinstance(locator_token, str):
            self._apply_locator(context, locator_token, payload)
        return StepResult.continue_(context)


__all__ = ['ResolveCitationStep']
