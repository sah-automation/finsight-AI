"""Deep module: Cascade step for the ingestion pipeline."""

from __future__ import annotations

import uuid
from typing import Any

from .pipeline_step_worker import (
    PipelineStepWorker,
    _awaitv,
    _coerce_company,
    _first,
)
from .step_context import (  # noqa: F401
    Context,
    IngestionContext,
    IngestionStepContext,
    PipelineContext,
    PipelineStepContext,
    StepContext,
)

__all__ = [
    'Cascade',
    'CascadeDeep',
    'CascadeModule',
    'CascadeStep',
    'CascadeStepDeep',
    'Context',
    'DeepCascade',
    'DeepCascadeStep',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineCascadeStep',
    'PipelineContext',
    'PipelineStepContext',
    'StepContext',
]

aliases = [
    'Cascade',
    'CascadeDeep',
    'CascadeModule',
    'CascadeStep',
    'CascadeStepDeep',
    'DeepCascade',
    'DeepCascadeStep',
    'PipelineCascadeStep',
]


class CascadeStep(PipelineStepWorker):
    """Invalidate caches, flag affected documents and publish cascade events."""

    step_name = 'cascade'

    def __init__(
        self,
        *,
        document_repository: Any = None,
        document_repo: Any = None,
        documents: Any = None,
        document_store: Any = None,
        metric_repository: Any = None,
        metrics: Any = None,
        metrics_repository: Any = None,
        figures: Any = None,
        extracted_metrics: Any = None,
        change_event_publisher: Any = None,
        event_publisher: Any = None,
        publisher: Any = None,
        change_publisher: Any = None,
        answer_cache: Any = None,
        cache: Any = None,
        answer_cache_port: Any = None,
        config: Any = None,
        settings: Any = None,
        configuration: Any = None,
        app_config: Any = None,
        state_store: Any = None,
        store: Any = None,
        context_store: Any = None,
        step_state_store: Any = None,
        container: Any = None,
        composition: Any = None,
        root: Any = None,
        app: Any = None,
        context: Any = None,
    ) -> None:
        def _pick(mapping: dict[str, Any]) -> Any:
            for value in mapping.values():
                if value is not None:
                    return value
            return None

        doc_repo = _pick(
            {
                'document_repository': document_repository,
                'document_repo': document_repo,
                'documents': documents,
                'document_store': document_store,
            }
        )
        metric_repo = _pick(
            {
                'metric_repository': metric_repository,
                'metrics': metrics,
                'metrics_repository': metrics_repository,
                'figures': figures,
                'extracted_metrics': extracted_metrics,
            }
        )
        pub = _pick(
            {
                'change_event_publisher': change_event_publisher,
                'event_publisher': event_publisher,
                'publisher': publisher,
                'change_publisher': change_publisher,
            }
        )
        cache_value = _pick(
            {
                'answer_cache': answer_cache,
                'cache': cache,
                'answer_cache_port': answer_cache_port,
            }
        )
        cfg = _pick(
            {
                'config': config,
                'settings': settings,
                'configuration': configuration,
                'app_config': app_config,
            }
        )
        st = _pick(
            {
                'state_store': state_store,
                'store': store,
                'context_store': context_store,
                'step_state_store': step_state_store,
            }
        )

        container_obj = None
        for candidate in (container, composition, root, app, context):
            if candidate is not None and not isinstance(candidate, (str, bytes, dict)):
                container_obj = candidate
                break

        if container_obj is not None:
            if doc_repo is None:
                doc_repo = getattr(container_obj, 'document_repository', doc_repo)
            if metric_repo is None:
                metric_repo = getattr(container_obj, 'metric_repository', metric_repo)
            if cache_value is None:
                cache_value = getattr(container_obj, 'answer_cache', cache_value)
            if pub is None:
                pub = getattr(container_obj, 'change_event_publisher', pub) or getattr(
                    container_obj, 'event_publisher', pub
                )
            if cfg is None:
                cfg = getattr(container_obj, 'config', cfg)

        super().__init__(
            document_repository=doc_repo,
            metric_repository=metric_repo,
            change_event_publisher=pub,
            answer_cache=cache_value,
            config=cfg,
            step_name='cascade',
        )
        self.state_store = st

    async def run(self, context: Any) -> Any:
        ctx = context
        company_id, version_id, document_id, key, version = await self._resolve(ctx)
        self._stash(ctx, company_id, version_id, document_id, key, version)

        request: Any = ctx if isinstance(ctx, dict) else {}
        if not isinstance(ctx, dict):
            for name in (
                'document_id',
                'documentId',
                'doc_id',
                'category',
                'document_category',
                'period',
                'reporting_period',
                'job_id',
                'jobId',
                'version',
            ):
                value = getattr(ctx, name, None)
                if value is not None and name not in request:
                    request[name] = value

        result = await self._step_cascade(
            company_id, version, version_id, document_id, key, request, {}
        )

        self._augment(ctx, result)
        await self._persist(ctx, version_id)
        return ctx

    async def _resolve(self, ctx: Any) -> tuple[Any, Any, Any, Any, Any]:
        company_id = _coerce_company(
            _first(ctx, 'company_id', 'company', 'tenant_id', default=None)
        )
        if company_id is None:
            raise ValueError('company_id is required')
        version_id = _first(ctx, 'version_id', 'document_version_id', 'id', default=None)
        document_id = _first(ctx, 'document_id', 'documentId', 'doc_id', default=None)
        key = _first(ctx, 'key', 'object_key', 's3_key', 'file_key', default='')
        version = _first(ctx, 'version', 'document_version', default=None)
        if version_id is None:
            version_id = str(uuid.uuid4())
        if key is None:
            key = ''
        if version is None:
            version = await self._get_version(company_id, version_id, document_id)
        return company_id, version_id, document_id, key, version

    def _stash(
        self, ctx: Any, company_id: Any, version_id: Any, document_id: Any, key: Any, version: Any
    ) -> None:
        for name, value in (
            ('company_id', company_id),
            ('version_id', version_id),
            ('document_id', document_id),
            ('key', key),
            ('version', version),
        ):
            try:
                setattr(ctx, name, value)
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx[name] = value

    def _augment(self, ctx: Any, result: Any) -> None:
        if not isinstance(result, dict):
            return
        affected = result.get('affected_documents', result.get('affected_document_ids'))
        mapping = {
            'status': result.get('status'),
            'version': result.get('version'),
            'cache_cleared': result.get('cache_cleared'),
            'cascade_triggered': result.get('cascade_triggered'),
            'affected_documents': affected,
            'affected_document_ids': affected,
            'affected_count': result.get('affected_count'),
            'cache_cleared_on_cascade': result.get('cache_cleared_on_cascade'),
        }
        for key, value in mapping.items():
            if value is None and key not in result and key not in ('affected_document_ids',):
                continue
            try:
                setattr(ctx, key, value)
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx[key] = value
        try:
            ctx.result = result
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['result'] = result

    async def _persist(self, ctx: Any, version_id: Any) -> None:
        if self.state_store is None:
            return
        try:
            await _awaitv(self.state_store.set(version_id, ctx))
            return
        except Exception:
            pass
        try:
            method = (
                getattr(self.state_store, 'save', None)
                or getattr(self.state_store, 'store', None)
                or getattr(self.state_store, 'put', None)
            )
            if callable(method):
                await _awaitv(method(version_id, ctx))
        except Exception:
            pass

    def __call__(self, context: Any) -> Any:
        return self.run(context)


Cascade = CascadeStep
CascadeDeep = CascadeStep
CascadeModule = CascadeStep
CascadeStepDeep = CascadeStep
DeepCascade = CascadeStep
DeepCascadeStep = CascadeStep
PipelineCascadeStep = CascadeStep
