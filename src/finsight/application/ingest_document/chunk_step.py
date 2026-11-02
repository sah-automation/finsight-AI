"""Deep module: Chunk step for the ingestion pipeline."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from .chunk_step_operations import ChunkStepOperations

if TYPE_CHECKING:
    from finsight.core.config.models import Config
    from finsight.domain.ports.chunk_repository import ChunkRepository
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

aliases = [
    'ChunkDeep',
    'ChunkModule',
    'ChunkStep',
    'ChunkStepDeep',
    'DeepChunkStep',
    'PipelineChunkStep',
]

__all__ = [
    'ChunkDeep',
    'ChunkModule',
    'ChunkStep',
    'ChunkStepDeep',
    'Context',
    'DeepChunkStep',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineChunkStep',
    'PipelineContext',
    'PipelineStepContext',
    'StepContext',
]


class ChunkStep(ChunkStepOperations, PipelineStepWorker):
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
        chunk_repository: ChunkRepository | None = None,
        chunks: Any = None,
        chunk_store: Any = None,
        document_chunks: Any = None,
        config: Config | None = None,
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
        delta_tracking: Any = None,
    ) -> None:
        super().__init__(
            reader=reader
            if reader is not None
            else (document_reader if document_reader is not None else primary_reader),
            page_router=page_router if page_router is not None else router,
            document_repository=document_repository
            if document_repository is not None
            else (document_repo if document_repo is not None else documents),
            chunk_repository=chunk_repository
            if chunk_repository is not None
            else (
                chunks
                if chunks is not None
                else (chunk_store if chunk_store is not None else document_chunks)
            ),
            config=config
            if config is not None
            else (
                settings
                if settings is not None
                else (configuration if configuration is not None else app_config)
            ),
            object_storage=object_storage
            if object_storage is not None
            else (storage if storage is not None else s3),
            page_router_enabled=page_router_enabled,
            step_name='chunk',
            **({'delta_tracking': delta_tracking} if delta_tracking is not None else {}),
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
        if delta_tracking is not None:
            try:
                self.delta_tracking = bool(delta_tracking)
            except Exception:  # noqa: BLE001
                pass

    async def run(self, context: Any) -> Any:
        company_id, version_id, document_id, key, version = await self._resolve(context)
        state = self._effective_state(version, context)
        if state in ('committed', 'done'):
            return await self._committed(context, version, version_id)
        if state in ('stored', 'received'):
            await self._update_state(version, company_id, version_id, 'processing')
        reader_result = await self._prepare_reader_result(context, company_id, version, key)
        delta_flag = self._resolve_delta_flag(context)
        chunks, chunk_entities = self._build_chunks(
            reader_result, company_id, document_id, version_id, version, context
        )
        removed, changed, unchanged, diff = await self._compute_chunk_diff(
            chunk_entities, company_id, document_id, version_id, delta_flag
        )
        self._augment_context(
            context,
            reader_result,
            chunks,
            chunk_entities,
            (changed, removed, delta_flag, diff, unchanged),
        )
        await self._update_state(
            version, company_id, version_id, 'processing', chunk_count=len(chunks)
        )
        await self._persist(context, version_id)
        return context

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
        self._stash(ctx, company_id, version_id, document_id, key, version)
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

    async def _prepare_reader_result(
        self, ctx: Any, company_id: Any, version: Any, key: str
    ) -> Any:
        reader_result = _first(ctx, 'reader_result', default=None)
        if reader_result is None:
            reader_result = await self._read(company_id, version, key)
            try:
                ctx.reader_result = reader_result
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx['reader_result'] = reader_result
        return reader_result

    def _resolve_delta_flag(self, ctx: Any) -> bool:
        delta_flag = _first(ctx, 'delta_tracking', default=None)
        if delta_flag is None:
            delta_flag = self.delta_tracking
        if delta_flag is None:
            delta_flag = _config_delta_tracking(self.config, {})
        try:
            return bool(delta_flag)
        except Exception:  # noqa: BLE001
            return True

    def _effective_state(self, version: Any, ctx: Any) -> str:
        state = self._version_state(version)
        if state in ('committed', 'done'):
            return state
        if bool(_first(ctx, 'committed', default=False)):
            return 'committed'
        status = _first(ctx, 'status', 'state', default=None)
        if isinstance(status, str) and status.strip().lower() in ('committed', 'done'):
            return status.strip().lower()
        return state

    async def _committed(self, ctx: Any, version: Any, version_id: Any) -> Any:
        for name, value in (
            ('status', 'committed'),
            ('committed', True),
            ('idempotent', True),
            ('idempotent_noop', True),
        ):
            try:
                setattr(ctx, name, value)
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx[name] = value
        await self._persist(ctx, version_id)
        return ctx

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


ChunkDeep = ChunkStep
ChunkStepDeep = ChunkStep
DeepChunkStep = ChunkStep
ChunkModule = ChunkStep
PipelineChunkStep = ChunkStep
