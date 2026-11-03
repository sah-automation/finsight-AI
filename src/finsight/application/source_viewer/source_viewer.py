# ruff: noqa: ANN401, B007, BLE001, C416, C901, E501, F401, F841, I001, N806, PERF403, PLC0415, PLR0912, PLR0913, PLR0915, PLR0917, RET504, RUF100, S110, SIM105, UP035
from __future__ import annotations

from typing import Any

from .source_viewer_context import SourceViewerContext
from .step_result import StepResult

from ._step_helpers import _coalesce, _normalize_version_key


def _step(value: Any, *names: str) -> Any:
    for name in names:
        if value is not None:
            return value
    return None


def _collect_steps(**kwargs: Any) -> tuple[Any, ...]:
    direct = [
        kwargs.get('authorize_step'),
        kwargs.get('resolve_citation_step'),
        kwargs.get('resolve_version_step'),
        kwargs.get('fetch_content_step'),
        kwargs.get('fetch_original_step'),
        kwargs.get('audit_step'),
    ]
    seq = kwargs.get('step_list')
    if seq is None:
        seq = kwargs.get('pipeline')
    if seq is None:
        seq = kwargs.get('steps')
    if isinstance(seq, dict):
        vals = list(seq.values())
        for i, v in enumerate(vals):
            if i < len(direct) and direct[i] is None:
                direct[i] = v
    elif isinstance(seq, (list, tuple)):
        for i, v in enumerate(seq):
            if i < len(direct) and direct[i] is None:
                direct[i] = v
    elif seq is not None:
        for i, name in enumerate(
            (
                'authorize_step',
                'resolve_citation_step',
                'resolve_version_step',
                'fetch_content_step',
                'fetch_original_step',
                'audit_step',
            )
        ):
            if direct[i] is None:
                direct[i] = getattr(seq, name, None)
    return tuple(direct)


class SourceViewer:
    def __init__(
        self,
        *,
        authorize_step: Any = None,
        resolve_citation_step: Any = None,
        resolve_version_step: Any = None,
        fetch_content_step: Any = None,
        fetch_original_step: Any = None,
        audit_step: Any = None,
        steps: Any = None,
        pipeline: Any = None,
        step_list: Any = None,
        tracing: Any = None,
        tracer: Any = None,
        tracing_port: Any = None,
    ) -> None:
        resolved = _collect_steps(
            authorize_step=authorize_step,
            resolve_citation_step=resolve_citation_step,
            resolve_version_step=resolve_version_step,
            fetch_content_step=fetch_content_step,
            fetch_original_step=fetch_original_step,
            audit_step=audit_step,
            steps=steps,
            pipeline=pipeline,
            step_list=step_list,
        )
        self._authorize_step = resolved[0]
        self._resolve_citation_step = resolved[1]
        self._resolve_version_step = resolved[2]
        self._fetch_content_step = resolved[3]
        self._fetch_original_step = resolved[4]
        self._audit_step = resolved[5]
        self.authorize_step = self._authorize_step
        self.resolve_citation_step = self._resolve_citation_step
        self.resolve_version_step = self._resolve_version_step
        self.fetch_content_step = self._fetch_content_step
        self.fetch_original_step = self._fetch_original_step
        self.audit_step = self._audit_step
        self.steps = [s for s in resolved]
        self.pipeline = list(self.steps)
        tracing_resolved = tracing if tracing is not None else tracer
        if tracing_resolved is None:
            tracing_resolved = tracing_port
        self._tracing = tracing_resolved
        self.tracing = self._tracing

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        context = self._coerce_context(*args, **kwargs)
        initial = {
            'document_id': getattr(context, 'document_id', None),
            'page': getattr(context, 'page', None),
            'citation': getattr(context, 'citation_input', None),
            'version_id': getattr(context, 'version_id', None),
            'company_id': getattr(context, 'company_id', None),
        }
        outcome = await self._run_steps(context)
        await self._run_audit(context, outcome)
        return self._result(context, outcome, initial)

    async def _run_steps(self, context: Any) -> str:
        outcome = 'success'
        specs = [
            ('authorize', self._authorize_step),
            ('resolve_citation', self._resolve_citation_step),
            ('resolve_version', self._resolve_version_step),
            ('fetch_content', self._fetch_content_step),
            ('fetch_original', self._fetch_original_step),
        ]
        for op_name, step in specs:
            if step is None:
                continue
            await self._trace(self._company_id(context), op_name)
            try:
                result = await step.run(context)
            except Exception as exc:  # pragma: no cover
                result = StepResult.stop_with_error(context, exc)
            if not isinstance(result, StepResult):
                continue
            if result.kind == 'continue':
                continue
            if result.kind == 'not_available':
                return 'not_available'
            if result.kind == 'error':
                return 'error'
        return outcome

    async def _run_audit(self, context: Any, outcome: str) -> None:
        await self._trace(self._company_id(context), 'audit')
        context.outcome = outcome
        if self._audit_step is not None:
            try:
                await self._audit_step.run(context)
            except Exception:
                pass

    def _result(self, context: Any, outcome: str, initial: dict[str, Any]) -> Any:
        from .models import SourceViewerResult

        if outcome == 'success':
            vobj = getattr(context, 'version_obj', None)
            cited_id = None
            try:
                cited_id = _normalize_version_key(vobj) if vobj is not None else None
            except Exception:
                cited_id = None
            text = getattr(context, 'text', None)
            if text is None:
                text = ''
            tables = getattr(context, 'tables', None)
            if not isinstance(tables, list):
                tables = list(tables) if tables is not None else []
            table_payload = getattr(context, 'table_payload', None)
            if table_payload is None and tables:
                table_payload = tables[0]
            needs_review = getattr(context, 'needs_review', None)
            if needs_review is None:
                needs_review = False
            newer_available = getattr(context, 'newer_available', None)
            if newer_available is None:
                newer_available = False
            original_available = getattr(context, 'original_available', None)
            if original_available is None:
                original_available = False
            result_obj = SourceViewerResult(
                status='available',
                document_id=_coalesce(
                    getattr(context, 'document_id', None), initial['document_id']
                ),
                document_title=getattr(context, 'document_title', None),
                title=getattr(context, 'document_title', None),
                document_version=_coalesce(initial['version_id'], cited_id),
                version=_coalesce(initial['version_id'], cited_id),
                version_id=_coalesce(initial['version_id'], cited_id),
                page_number=_coalesce(getattr(context, 'page', None), initial['page']),
                page=_coalesce(getattr(context, 'page', None), initial['page']),
                content_type=_coalesce(getattr(context, 'content_type', None), 'text'),
                text=text,
                table=table_payload,
                tables=tables,
                highlight=getattr(context, 'highlight', None),
                needs_review=bool(needs_review),
                newer_version_available=bool(newer_available),
                newer_version_id=getattr(context, 'newer_id', None),
                original_available=bool(original_available),
                original_link=_coalesce(
                    getattr(context, 'signed_original_link', None),
                    getattr(context, 'original_link', None),
                ),
                citation=_coalesce(getattr(context, 'citation_input', None), initial['citation']),
                citation_locator=_coalesce(
                    getattr(context, 'locator_token', None), getattr(context, 'locator', None)
                ),
                locator=_coalesce(
                    getattr(context, 'locator_token', None), getattr(context, 'locator', None)
                ),
                company_id=_coalesce(getattr(context, 'company_id', None), initial['company_id']),
                user_id=getattr(context, 'user_id', None),
                role=getattr(context, 'role', None),
                trace_id=getattr(context, 'trace_id', None),
                outcome='success',
                result='available',
            )
        else:
            locator_token = _coalesce(
                getattr(context, 'locator_token', None), getattr(context, 'locator', None)
            )
            result_obj = SourceViewerResult(
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
                citation=_coalesce(getattr(context, 'citation_input', None), initial['citation']),
                citation_locator=locator_token,
                locator=locator_token,
                company_id=_coalesce(getattr(context, 'company_id', None), initial['company_id']),
                user_id=getattr(context, 'user_id', None),
                role=getattr(context, 'role', None),
                trace_id=getattr(context, 'trace_id', None),
                outcome='error' if outcome == 'error' else 'not_available',
                result='not_available',
            )
        context.outcome = outcome
        context.result_obj = result_obj
        if outcome != 'success':
            result_obj.status = 'not_available'
            result_obj.outcome = 'error' if outcome == 'error' else 'not_available'
            result_obj.result = 'not_available'
        return result_obj

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return await self.run(*args, **kwargs)

    async def view(self, *args: Any, **kwargs: Any) -> Any:
        return await self.run(*args, **kwargs)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self.run(*args, **kwargs)

    def _coerce_context(self, *args: Any, **kwargs: Any) -> SourceViewerContext:
        first = args[0] if args else None
        if isinstance(first, SourceViewerContext):
            return first
        from ._request_to_context import _build_source_viewer_context as _builder

        return _builder(*args, **kwargs)

    def _company_id(self, context: Any) -> Any:
        value = getattr(context, 'company_id', None)
        if value is None and isinstance(context, dict):
            value = context.get('company_id')
        if value is None and hasattr(context, 'extras') and isinstance(context.extras, dict):
            value = context.extras.get('company_id')
        return value

    async def _trace(self, company_id: Any, operation: str) -> None:
        tracer = self._tracing
        if tracer is None:
            return
        try:
            method = getattr(tracer, 'start_span', None)
            if method is None:
                method = getattr(tracer, 'span', None)
            if not callable(method):
                return
            result = method(company_id, operation)
            if hasattr(result, '__await__'):
                await result
        except Exception:
            return
