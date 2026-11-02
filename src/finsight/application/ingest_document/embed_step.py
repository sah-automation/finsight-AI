"""Deep module: Embed step for the ingestion pipeline."""

from __future__ import annotations

import uuid
from typing import Any

from .embed_step_operations import EmbedStepOperations
from .pipeline_step_worker import (
    PipelineStepWorker,
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
    'DeepEmbedStep',
    'Embed',
    'EmbedDeep',
    'EmbedModule',
    'EmbedStep',
    'EmbedStepDeep',
    'EmbeddingStep',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineContext',
    'PipelineEmbedStep',
    'PipelineStepContext',
    'StepContext',
]

aliases = [
    'DeepEmbedStep',
    'Embed',
    'EmbedDeep',
    'EmbedModule',
    'EmbedStep',
    'EmbedStepDeep',
    'EmbeddingStep',
    'PipelineEmbedStep',
]


class EmbedStep(EmbedStepOperations, PipelineStepWorker):
    """Embed chunks via an injected embedding port and augment a step context."""

    def __init__(
        self,
        *,
        embedding: Any = None,
        embedding_adapter: Any = None,
        embedder: Any = None,
        embeddings: Any = None,
        embedding_port: Any = None,
        port: Any = None,
        adapter: Any = None,
        provider: Any = None,
        embedding_provider: Any = None,
        chunk_repository: Any = None,
        chunks: Any = None,
        chunk_store: Any = None,
        document_chunks: Any = None,
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
        delta_tracking: Any = None,
    ) -> None:
        resolved_embedding = embedding
        if resolved_embedding is None:
            resolved_embedding = (
                embedding_adapter
                if embedding_adapter is not None
                else (
                    embedder
                    if embedder is not None
                    else (
                        embeddings
                        if embeddings is not None
                        else (
                            embedding_port
                            if embedding_port is not None
                            else (
                                port
                                if port is not None
                                else (
                                    adapter
                                    if adapter is not None
                                    else (
                                        embedding_provider
                                        if embedding_provider is not None
                                        else provider
                                    )
                                )
                            )
                        )
                    )
                )
            )
        resolved_chunks = chunk_repository
        if resolved_chunks is None:
            resolved_chunks = (
                chunks
                if chunks is not None
                else (chunk_store if chunk_store is not None else document_chunks)
            )
        super().__init__(
            embedding=resolved_embedding,
            chunk_repository=resolved_chunks,
            document_repository=(
                document_repository
                if document_repository is not None
                else (document_repo if document_repo is not None else documents)
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
            step_name='embed',
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
        ctx = context
        company_id, version_id, document_id, key, version = await self._resolve(ctx)
        self._stash(ctx, company_id, version_id, document_id, key, version)

        state = self._effective_state(version, ctx)
        if state in ('committed', 'done'):
            return await self._committed(ctx, version, version_id)

        if state in ('stored', 'received'):
            await self._update_state(version, company_id, version_id, 'processing')

        chunks = await self._ensure_chunks(ctx, company_id, version_id, key, version)
        texts = self._as_texts(chunks)
        vectors = await self._embed_all(texts, company_id)
        self._augment(ctx, chunks, vectors)
        await self._update_state(
            version, company_id, version_id, 'processing', embedded_count=len(vectors)
        )
        await self._persist(ctx, version_id)
        return ctx

    async def _resolve(self, ctx: Any) -> tuple[Any, Any, Any, Any, Any]:
        company_id = _coerce_company(
            _first(ctx, 'company_id', 'company', 'tenant_id', default=None)
        )
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
        try:
            ctx.company_id = company_id
            ctx.version_id = version_id
            ctx.document_id = document_id
            ctx.key = key
            ctx.version = version
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['company_id'] = company_id
                ctx['version_id'] = version_id
                ctx['document_id'] = document_id
                ctx['key'] = key
                ctx['version'] = version

    async def _get_version(self, company_id: Any, version_id: Any, document_id: Any = None) -> Any:
        from finsight.domain.entities.document_version import DocumentVersion

        # EmbedStep must not read a document; version state comes from context or a
        # synthetic in-memory version only.
        return DocumentVersion(
            company_id=company_id,
            id=version_id,
            document_id=document_id,
            state='stored',
            extras={},
        )

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

    def __call__(self, context: Any) -> Any:
        return self.run(context)


DeepEmbedStep = EmbedStep
Embed = EmbedStep
EmbedDeep = EmbedStep
EmbedModule = EmbedStep
EmbedStepDeep = EmbedStep
EmbeddingStep = EmbedStep
PipelineEmbedStep = EmbedStep
