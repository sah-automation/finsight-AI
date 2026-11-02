"""Deep module: Metric step for the ingestion pipeline."""

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
    'Context',
    'DeepMetric',
    'DeepMetricStep',
    'IngestionContext',
    'IngestionStepContext',
    'Metric',
    'MetricDeep',
    'MetricModule',
    'MetricStep',
    'MetricStepDeep',
    'PipelineContext',
    'PipelineMetricStep',
    'PipelineStepContext',
    'StepContext',
]

aliases = [
    'DeepMetric',
    'DeepMetricStep',
    'Metric',
    'MetricDeep',
    'MetricModule',
    'MetricStep',
    'MetricStepDeep',
    'PipelineMetricStep',
]


class MetricStep(PipelineStepWorker):
    """Extract metrics from context and persist them through injected ports."""

    step_name = 'metric'

    def __init__(
        self,
        *,
        metric_repository: Any = None,
        metrics: Any = None,
        metrics_repository: Any = None,
        figures: Any = None,
        extracted_metrics: Any = None,
        document_repository: Any = None,
        document_repo: Any = None,
        documents: Any = None,
        document_store: Any = None,
        reader: Any = None,
        document_reader: Any = None,
        primary_reader: Any = None,
        page_router: Any = None,
        router: Any = None,
        config: Any = None,
        settings: Any = None,
        configuration: Any = None,
        app_config: Any = None,
        object_storage: Any = None,
        storage: Any = None,
        s3: Any = None,
        page_router_enabled: Any = None,
        state_store: Any = None,
        store: Any = None,
        context_store: Any = None,
        step_state_store: Any = None,
        container: Any = None,
        composition: Any = None,
        root: Any = None,
        app: Any = None,
        context: Any = None,
        delta_tracking: Any = None,
    ) -> None:
        def _pick(mapping: dict[str, Any]) -> Any:
            for value in mapping.values():
                if value is not None:
                    return value
            return None

        metric_repo = _pick(
            {
                'metric_repository': metric_repository,
                'metrics': metrics,
                'metrics_repository': metrics_repository,
                'figures': figures,
                'extracted_metrics': extracted_metrics,
            }
        )
        doc_repo = _pick(
            {
                'document_repository': document_repository,
                'document_repo': document_repo,
                'documents': documents,
                'document_store': document_store,
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
            if metric_repo is None:
                metric_repo = getattr(container_obj, 'metric_repository', metric_repo)
            if doc_repo is None:
                doc_repo = getattr(container_obj, 'document_repository', doc_repo)
            if cfg is None:
                cfg = getattr(container_obj, 'config', cfg)

        super().__init__(
            metric_repository=metric_repo,
            document_repository=doc_repo,
            reader=reader
            if reader is not None
            else (document_reader if document_reader is not None else primary_reader),
            page_router=page_router if page_router is not None else router,
            config=cfg,
            object_storage=object_storage
            if object_storage is not None
            else (storage if storage is not None else s3),
            page_router_enabled=page_router_enabled,
            step_name='metric',
            **({'delta_tracking': delta_tracking} if delta_tracking is not None else {}),
        )
        self.state_store = st

    async def run(self, context: Any) -> Any:
        ctx = context
        company_id, version_id, document_id, key, version = await self._resolve(ctx)
        self._stash(ctx, company_id, version_id, document_id, key, version)

        metrics = await self._resolve_metrics(ctx, company_id, version, key)
        persisted = await self._persist_metrics(
            company_id, version_id, metrics if metrics is not None else []
        )

        self._augment(ctx, version, metrics, persisted)
        await self._persist(ctx, version_id)
        return ctx

    async def _resolve_metrics(self, ctx: Any, company_id: Any, version: Any, key: str) -> Any:
        metrics = _first(ctx, 'metrics', 'extracted_metrics', default=None)
        reader_result = _first(ctx, 'reader_result', default=None)
        if metrics is None:
            if reader_result is None:
                reader_result = await self._read(company_id, version, key)
                try:
                    ctx.reader_result = reader_result
                except Exception:  # noqa: BLE001
                    if isinstance(ctx, dict):
                        ctx['reader_result'] = reader_result
            metrics = self._extract_metrics(reader_result)
        return metrics

    def _augment(self, ctx: Any, version: Any, metrics: Any, persisted: bool) -> None:
        try:
            ctx.version = version
            if metrics is not None:
                ctx.metrics = metrics
            ctx.persisted = persisted
            ctx.status = 'metrics_persisted'
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['version'] = version
                if metrics is not None:
                    ctx['metrics'] = metrics
                ctx['persisted'] = persisted
                ctx['status'] = 'metrics_persisted'

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

    async def _persist(self, ctx: Any, version_id: Any) -> None:
        if self.state_store is None:
            return
        try:
            await _awaitv(self.state_store.set(version_id, ctx))
            return
        except Exception:  # noqa: BLE001
            pass
        try:
            method = (
                getattr(self.state_store, 'save', None)
                or getattr(self.state_store, 'store', None)
                or getattr(self.state_store, 'put', None)
            )
            if callable(method):
                await _awaitv(method(version_id, ctx))
        except Exception:  # noqa: BLE001
            pass

    def __call__(self, context: Any) -> Any:
        return self.run(context)


Metric = MetricStep
MetricDeep = MetricStep
MetricModule = MetricStep
MetricStepDeep = MetricStep
DeepMetric = MetricStep
DeepMetricStep = MetricStep
PipelineMetricStep = MetricStep
