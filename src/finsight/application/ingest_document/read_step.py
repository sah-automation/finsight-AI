"""Deep module: Read step for the ingestion pipeline."""

from __future__ import annotations

import uuid
from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult

from .pipeline_step_worker import (
    PipelineStepWorker,
    _awaitv,
    _coerce_company,
    _config_delta_tracking,
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
    'IngestionContext',
    'PipelineContext',
    'PipelineReadStep',
    'PipelineStepContext',
    'Read',
    'ReadStep',
    'ReadStepDeep',
    'ReaderStep',
    'StepContext',
]

aliases = ['PipelineReadStep', 'Read', 'ReadStep', 'ReadStepDeep', 'ReaderStep']


class ReadStep(PipelineStepWorker):
    """Read a document via injected ports and augment a step context."""

    def __init__(
        self,
        *,
        reader: Any = None,
        document_reader: Any = None,
        primary_reader: Any = None,
        page_router: Any = None,
        router: Any = None,
        document_repository: Any = None,
        document_repo: Any = None,
        documents: Any = None,
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
    ) -> None:
        super().__init__(
            reader=reader
            if reader is not None
            else (document_reader if document_reader is not None else primary_reader),
            page_router=page_router if page_router is not None else router,
            document_repository=(
                document_repository
                if document_repository is not None
                else (document_repo if document_repo is not None else documents)
            ),
            config=(
                config
                if config is not None
                else (
                    settings
                    if settings is not None
                    else (configuration if configuration is not None else app_config)
                )
            ),
            object_storage=(
                object_storage
                if object_storage is not None
                else (storage if storage is not None else s3)
            ),
            page_router_enabled=page_router_enabled,
            step_name='read',
        )
        self.state_store = (
            state_store
            if state_store is not None
            else (
                store
                if store is not None
                else (context_store if context_store is not None else step_state_store)
            )
        )

    async def run(self, context: Any) -> Any:
        ctx = context
        company_id, version_id, document_id, key, version = await self._resolve(ctx)
        self._stash(ctx, company_id, version_id, document_id, key, version)

        state = self._version_state(version)
        if state in ('committed', 'done'):
            return await self._committed(ctx, version, version_id)

        if state in ('stored', 'received'):
            await self._update_state(version, company_id, version_id, 'processing')

        reader_result = await self._read(company_id, version, key)
        metrics = self._extract_metrics(reader_result)
        await self._update_state(
            version,
            company_id,
            version_id,
            'processing',
            extracted_text=reader_result.text if isinstance(reader_result, ReaderResult) else None,
            metrics_extracted=len(metrics),
        )
        delta_flag = _config_delta_tracking(self.config, {})
        branch = 'delta' if delta_flag else 'full_reprocess'
        self._augment(ctx, reader_result, metrics, delta_flag, branch)
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
        try:
            ctx.company_id = company_id
            ctx.version_id = version_id
            ctx.document_id = document_id
            ctx.key = key
            ctx.version = version
        except Exception:  # noqa: BLE001, S110
            pass

    async def _committed(self, ctx: Any, version: Any, version_id: Any) -> Any:
        try:
            ctx.status = 'committed'
            ctx.committed = True
            ctx.idempotent = True
            ctx.idempotent_noop = True
        except Exception:  # noqa: BLE001, S110
            if isinstance(ctx, dict):
                ctx['status'] = 'committed'
                ctx['committed'] = True
                ctx['idempotent'] = True
                ctx['idempotent_noop'] = True
        await self._persist(ctx, version_id)
        return ctx

    def _augment(
        self, ctx: Any, reader_result: Any, metrics: Any, delta_flag: bool, branch: str
    ) -> None:
        try:
            ctx.reader_result = reader_result
            ctx.metrics = metrics
            ctx.delta_tracking = delta_flag
            ctx.branch = branch
            ctx.status = 'processing'
        except Exception:  # noqa: BLE001, S110
            if isinstance(ctx, dict):
                ctx['reader_result'] = reader_result
                ctx['metrics'] = metrics
                ctx['delta_tracking'] = delta_flag
                ctx['branch'] = branch
                ctx['status'] = 'processing'

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


Read = ReadStep
ReaderStep = ReadStep
ReadStepDeep = ReadStep
PipelineReadStep = ReadStep
