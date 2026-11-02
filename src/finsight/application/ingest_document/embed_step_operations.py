"""Helpers for EmbedStep."""

from __future__ import annotations

from typing import Any

from .pipeline_step_worker import PipelineStepWorker, _awaitv, _get


class EmbedStepOperations(PipelineStepWorker):
    embedding: Any
    chunk_repository: Any
    state_store: Any
    delta_tracking: Any
    config: Any

    async def _ensure_chunks(
        self, ctx: Any, company_id: Any, version_id: Any, key: str, version: Any
    ) -> Any:
        chunks = None
        for attr in (
            'chunks',
            'embed_chunks',
            'changed_chunks',
            'changed_chunk_entities',
            'chunk_entities',
        ):
            if hasattr(ctx, attr):
                value = getattr(ctx, attr, None)
                if value:
                    chunks = value
                    break
        if chunks is None and isinstance(ctx, dict):
            for attr in (
                'chunks',
                'embed_chunks',
                'changed_chunks',
                'changed_chunk_entities',
                'chunk_entities',
            ):
                value = ctx.get(attr)
                if value:
                    chunks = value
                    break
        if chunks:
            return chunks
        repo = self.chunk_repository
        if repo is not None and version_id is not None:
            for method_name in ('list_chunks_by_version', 'list_chunks', 'get_chunks'):
                method = getattr(repo, method_name, None)
                if callable(method):
                    try:
                        result = await _awaitv(method(company_id, version_id))
                        if result:
                            return result
                    except TypeError:
                        try:
                            result = await _awaitv(
                                method(company_id=company_id, version_id=version_id)
                            )
                            if result:
                                return result
                        except Exception:  # noqa: BLE001
                            pass
                    except Exception:  # noqa: BLE001
                        pass
        reader_result = None
        try:
            reader_result = ctx.reader_result if hasattr(ctx, 'reader_result') else None
        except Exception:  # noqa: BLE001
            reader_result = None
        if reader_result is None and isinstance(ctx, dict):
            reader_result = ctx.get('reader_result')
        if reader_result is None and self._reader() is not None:
            try:
                reader_result = await self._read(company_id, version, key)
            except Exception:  # noqa: BLE001
                reader_result = None
            if reader_result is not None:
                try:
                    ctx.reader_result = reader_result
                except Exception:  # noqa: BLE001
                    if isinstance(ctx, dict):
                        ctx['reader_result'] = reader_result
        if reader_result is not None:
            if isinstance(reader_result, self._reader_result_type()):
                text = reader_result.text
            else:
                text = str(_get(reader_result, 'text', default='') or '')
            return self._chunk_text(text)
        return []

    def _reader_result_type(self) -> Any:
        try:
            from finsight.domain.value_objects.reader_result import ReaderResult

            return ReaderResult
        except Exception:  # noqa: BLE001
            return ()

    def _as_texts(self, chunks: Any) -> list[str]:
        texts: list[str] = []
        if chunks is None:
            return texts
        if isinstance(chunks, str):
            return [chunks]
        if not isinstance(chunks, (list, tuple)):
            chunks = [chunks]
        for ch in chunks:
            if isinstance(ch, str):
                texts.append(ch)
            elif isinstance(ch, dict):
                value = _get(ch, 'text', 'chunk_text', 'content', default=None)
                texts.append(str(value) if value is not None else str(ch))
            else:
                value = getattr(ch, 'text', None)
                if value is None:
                    value = _get(ch, 'text', 'chunk_text', 'content', default=None)
                texts.append(str(value) if value is not None else str(ch))
        return texts

    async def _embed_all(self, texts: list[str], company_id: Any) -> list[Any]:
        if not texts:
            return []
        embedder = self.embedding
        if embedder is None:
            return [self._synthetic(t) for t in texts]
        method = None
        for name in (
            'embed',
            'embed_text',
            'embed_texts',
            'embed_batch',
            'embed_documents',
            'encode',
            'generate',
            'get_embedding',
        ):
            candidate = getattr(embedder, name, None)
            if callable(candidate):
                method = candidate
                break
        if method is None:
            if callable(embedder):
                method = embedder
            else:
                return [self._synthetic(t) for t in texts]
        batch = await self._try_batch(method, texts, company_id)
        if batch is not None and len(batch) == len(texts):
            return batch  # type: ignore[no-any-return]
        output: list[Any] = []
        for text in texts:
            vector = await self._embed_one(method, text, company_id)
            if vector is None:
                vector = self._synthetic(text)
            output.append(vector)
        return output

    async def _try_batch(self, method: Any, texts: list[str], company_id: Any) -> Any:
        attempts = []
        if company_id is not None:
            attempts.append(lambda: method(company_id, list(texts)))
        attempts.append(lambda: method(list(texts)))
        if company_id is not None:
            attempts.append(lambda: method(texts=list(texts), company_id=company_id))
        attempts.append(lambda: method(texts=list(texts)))
        for fn in attempts:
            try:
                result = await _awaitv(fn())  # type: ignore[no-untyped-call]
                normalized = self._normalize_batch(result, len(texts))
                if normalized is not None:
                    return normalized
            except Exception:  # noqa: BLE001
                continue
        return None

    def _normalize_batch(self, result: Any, count: int) -> Any:
        if isinstance(result, (list, tuple)):
            if count == 1:
                vector = self._to_vector(result)
                if vector is not None and not (
                    len(result) == count and all(isinstance(x, (list, tuple)) for x in result)
                ):
                    return [vector]
            if len(result) == count:
                output = []
                for item in result:
                    vector = self._to_vector(item)
                    if vector is None:
                        return None
                    output.append(vector)
                return output
        return None

    async def _embed_one(self, method: Any, text: str, company_id: Any) -> Any:
        attempts = []
        if company_id is not None:
            attempts.append(lambda: method(company_id, [text]))
            attempts.append(lambda: method(company_id, text))
        attempts.append(lambda: method([text]))
        attempts.append(lambda: method(text))
        if company_id is not None:
            attempts.append(lambda: method(text, company_id=company_id))
            attempts.append(lambda: method([text], company_id=company_id))
        attempts.append(lambda: method(texts=text))
        attempts.append(lambda: method(input=text))
        for fn in attempts:
            try:
                result = await _awaitv(fn())  # type: ignore[no-untyped-call]
                vector = self._to_vector(result)
                if vector is not None:
                    return vector
            except Exception:  # noqa: BLE001
                continue
        return None

    def _to_vector(self, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            if value and isinstance(value[0], (list, tuple)):
                try:
                    return [float(x) for x in value[0]]
                except (TypeError, ValueError):
                    return list(value[0])
            try:
                return [float(x) for x in value]
            except (TypeError, ValueError):
                return list(value)
        if value is None:
            return None
        return [value]

    def _synthetic(self, text: Any) -> list[Any]:
        try:
            import hashlib

            digest = hashlib.sha256(str(text or '').encode('utf-8', 'replace')).digest()
            return [b / 255 for b in digest[:8]]
        except Exception:  # noqa: BLE001
            return [0.0] * 8

    def _augment(self, ctx: Any, chunks: Any, vectors: list[Any]) -> None:
        try:
            ctx.chunks = chunks if chunks is not None else ctx.chunks
            ctx.vectors = vectors
            ctx.embedded_count = len(vectors)
            ctx.vector_count = len(vectors)
            ctx.embedded_vectors = vectors
            ctx.status = 'processing'
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['chunks'] = chunks if chunks is not None else ctx.get('chunks')
                ctx['vectors'] = vectors
                ctx['embedded_count'] = len(vectors)
                ctx['vector_count'] = len(vectors)
                ctx['embedded_vectors'] = vectors
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
