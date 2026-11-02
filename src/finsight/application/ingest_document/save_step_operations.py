"""Deep module operations helpers for the Save step."""

from __future__ import annotations

import uuid
from typing import Any

from .pipeline_step_worker import (
    _IN_MEMORY_CHUNKS,
    _IN_MEMORY_METRICS,
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


class SaveStepOperations(PipelineStepWorker):
    state_store: Any

    async def run(self, context: Any) -> Any:
        ctx = context
        company_id, version_id, document_id, key, version = await self._resolve(ctx)
        self._stash(ctx, company_id, version_id, document_id, key, version)

        state = self._effective_state(version, ctx)
        if state in ('committed', 'done', 'stored_complete'):
            return await self._committed(ctx, version, version_id)

        # Prepare in-memory state so the inherited transactional logic can run
        # against a context that has been fully populated without re-reading.
        self._seed_in_memory(ctx, company_id, version_id, document_id, version, key)

        result = await self._step_save(
            company_id,
            version,
            version_id,
            document_id,
            key,
            ctx,
            {},
        )

        await self._augment(ctx, result)
        await self._persist(ctx, version_id)
        return ctx

    def _effective_state(self, version: Any, ctx: Any) -> str:
        state = self._version_state(version)
        if state in ('committed', 'done', 'stored_complete'):
            return state
        if bool(_first(ctx, 'committed', default=False)):
            return 'committed'
        status = _first(ctx, 'status', 'state', default=None)
        if isinstance(status, str) and status.strip().lower() in ('committed', 'done'):
            return status.strip().lower()
        return state

    async def _resolve(self, ctx: Any) -> Any:
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

    def _seed_in_memory(
        self,
        ctx: Any,
        company_id: Any,
        version_id: Any,
        document_id: Any,
        version: Any,
        key: Any,
    ) -> None:
        rid = str(version_id)
        reader_data = _IN_MEMORY_CHUNKS.get(rid, {})
        if not isinstance(reader_data, dict):
            reader_data = {}

        chunks = _first(ctx, 'chunks', default=None)
        if chunks is None:
            chunks = reader_data.get('chunks', [])
        chunk_entities = _first(ctx, 'chunk_entities', default=None)
        if chunk_entities is None:
            chunk_entities = reader_data.get('chunk_entities', []) or []
        changed = _first(ctx, 'changed_chunk_entities', default=None)
        if changed is None:
            changed = reader_data.get('changed_chunk_entities', []) or list(chunk_entities)
        vectors = _first(ctx, 'vectors', default=None)
        if vectors is None:
            vectors = reader_data.get('vectors', [])
        removed = _first(ctx, 'removed_chunk_ids', default=None)
        if removed is None:
            removed = reader_data.get('removed_chunk_ids', [])
        metrics = _first(ctx, 'metrics', default=None)
        if metrics is None:
            metrics = reader_data.get('metrics')
        if metrics is None:
            metrics = _IN_MEMORY_METRICS.get(rid, [])
        reader_result = _first(ctx, 'reader_result', default=None)
        if reader_result is None:
            reader_result = reader_data.get('reader_result')

        reader_data.setdefault('chunks', chunks or [])
        reader_data['chunk_entities'] = chunk_entities or []
        reader_data['changed_chunk_entities'] = changed or []
        reader_data['changed_chunks'] = [
            getattr(c, 'text', c) if not isinstance(c, str) else c for c in (changed or [])
        ]
        reader_data['embed_chunks'] = reader_data['changed_chunks']
        reader_data['vectors'] = vectors or []
        reader_data['removed_chunk_ids'] = removed or []
        if reader_result is not None:
            reader_data['reader_result'] = reader_result
        reader_data.setdefault('document_tables', reader_data.get('document_tables', []))
        _IN_MEMORY_CHUNKS[rid] = reader_data
        if metrics is not None:
            _IN_MEMORY_METRICS.setdefault(rid, metrics)

    async def _committed(self, ctx: Any, version: Any, version_id: Any) -> Any:
        rid = str(version_id)
        reader_data = _IN_MEMORY_CHUNKS.get(rid, {})
        if not isinstance(reader_data, dict):
            reader_data = {}
        chunks = _first(ctx, 'chunks', default=None)
        if chunks is None:
            chunks = reader_data.get('chunks', [])
        chunk_entities = _first(ctx, 'chunk_entities', default=None)
        if chunk_entities is None:
            chunk_entities = reader_data.get('chunk_entities', []) or []
        vectors = _first(ctx, 'vectors', default=None)
        if vectors is None:
            vectors = reader_data.get('vectors', [])
        metrics = _first(ctx, 'metrics', default=None)
        if metrics is None:
            metrics = reader_data.get('metrics')
        if metrics is None:
            metrics = _IN_MEMORY_METRICS.get(rid, [])
        document_tables = reader_data.get('document_tables', [])
        for name, value in (
            ('status', 'committed'),
            ('committed', True),
            ('idempotent', True),
            ('idempotent_noop', True),
            ('no_duplicate_side_effects', True),
            ('chunk_count', len(chunk_entities) or len(chunks)),
            ('vector_count', len(vectors)),
            ('metric_count', len(metrics) if isinstance(metrics, list) else 0),
            ('table_count', len(document_tables or [])),
            ('cache_cleared', False),
            ('change_event_published', False),
        ):
            try:
                setattr(ctx, name, value)
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx[name] = value
        await self._persist(ctx, version_id)
        return ctx

    async def _augment(self, ctx: Any, result: Any) -> None:
        if not isinstance(result, dict):
            return
        mapping = {
            'status': result.get('status'),
            'committed': result.get('committed'),
            'chunk_count': result.get('chunk_count'),
            'vector_count': result.get('vector_count'),
            'metric_count': result.get('metric_count'),
            'table_count': result.get('table_count'),
            'previous_version_id': result.get('previous_version_id'),
            'superseded_version_id': result.get('superseded_version_id'),
            'removed_count': result.get('removed_count'),
            'document_stamp': result.get('document_stamp'),
            'stamp': result.get('stamp'),
            'stamp_value': result.get('stamp_value'),
            'cache_cleared': result.get('cache_cleared'),
            'change_event_published': result.get('change_event_published'),
            'idempotent': result.get('idempotent'),
            'idempotent_noop': result.get('idempotent_noop'),
        }
        for key, value in mapping.items():
            if value is None and key not in result:
                continue
            try:
                setattr(ctx, key, value)
            except Exception:  # noqa: BLE001
                if isinstance(ctx, dict):
                    ctx[key] = value

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
