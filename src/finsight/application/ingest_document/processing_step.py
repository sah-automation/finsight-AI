"""Deep module: default Processing step for the ingestion pipeline."""

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
    'DeepProcessing',
    'DeepProcessingStep',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineContext',
    'PipelineProcessingStep',
    'PipelineStepContext',
    'Processing',
    'ProcessingDeep',
    'ProcessingModule',
    'ProcessingStep',
    'ProcessingStepDeep',
    'StepContext',
]

aliases = [
    'DeepProcessing',
    'DeepProcessingStep',
    'Processing',
    'ProcessingDeep',
    'ProcessingModule',
    'ProcessingStep',
    'ProcessingStepDeep',
    'PipelineProcessingStep',
]


class ProcessingStep(PipelineStepWorker):
    """Perform the default state transition and report processing status."""

    step_name = 'processing'

    def __init__(
        self,
        *,
        document_repository: Any = None,
        document_repo: Any = None,
        documents: Any = None,
        document_store: Any = None,
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
        delta_tracking: Any = None,
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
            if cfg is None:
                cfg = getattr(container_obj, 'config', cfg)

        super().__init__(
            document_repository=doc_repo,
            config=cfg,
            step_name='processing',
            **({'delta_tracking': delta_tracking} if delta_tracking is not None else {}),
        )
        self.state_store = st

    async def run(self, context: Any) -> Any:
        """Execute this pipeline step."""
        ctx = context
        company_id, version_id, document_id, key, version = await self._resolve(ctx)
        self._stash(ctx, company_id, version_id, document_id, key, version)

        await self._update_state(version, company_id, version_id, 'processing')

        try:
            ctx.version = version
            ctx.status = 'processing'
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['version'] = version
                ctx['status'] = 'processing'
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


Processing = ProcessingStep
ProcessingDeep = ProcessingStep
ProcessingModule = ProcessingStep
ProcessingStepDeep = ProcessingStep
DeepProcessing = ProcessingStep
DeepProcessingStep = ProcessingStep
PipelineProcessingStep = ProcessingStep
