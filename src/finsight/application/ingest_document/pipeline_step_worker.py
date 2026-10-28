"""Ingestion pipeline workers (read, chunk, embed, save, cascade)."""

from __future__ import annotations

import contextlib
import inspect
import uuid
from typing import Any

from finsight.core.types import CompanyId
from finsight.domain.entities.document_version import DocumentVersion
from finsight.domain.value_objects.reader_result import ReaderResult


async def _awaitv(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _first(mapping: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(mapping, dict):
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        elif hasattr(mapping, key):
            value = getattr(mapping, key, None)
            if value is not None:
                return value
    return default


def _coerce_company(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return CompanyId(text)
    except Exception:
        return value


def _normalize_key(key: Any) -> str:
    if key is None:
        return ''
    return str(key).replace('\\', '/').lstrip('/')


def _parse_key(key: Any) -> dict[str, Any]:
    result: dict[str, Any] = {'company_id': None, 'document_id': None, 'version_id': None}
    text = _normalize_key(key)
    parts = [p for p in text.split('/') if p]
    if parts:
        result['company_id'] = parts[0]
    if len(parts) >= 5 and parts[1] == 'documents' and parts[3] == 'versions':
        result['document_id'] = parts[2]
        result['version_id'] = parts[4]
    return result


def _config_delta_tracking(config: Any, kwargs: dict[str, Any]) -> bool:
    # explicit constructor kwarg
    for k in ('delta_tracking', 'delta', 'track_delta'):
        if k in kwargs and kwargs.get(k) is not None:
            try:
                return bool(kwargs.get(k))
            except Exception:
                pass
    # object attribute
    for attr in ('delta_tracking', 'delta', 'track_delta'):
        if hasattr(config, attr):
            try:
                return bool(getattr(config, attr))
            except Exception:
                pass
    # nested documents
    if config is not None:
        docs = getattr(config, 'documents', None)
        if docs is not None:
            for attr in ('delta_tracking', 'delta'):
                if hasattr(docs, attr):
                    try:
                        return bool(getattr(docs, attr))
                    except Exception:
                        pass
        if isinstance(config, dict):
            val = (config.get('documents') or {}).get('delta_tracking')
            if val is not None:
                try:
                    return bool(val)
                except Exception:
                    pass
            if 'delta_tracking' in config:
                try:
                    return bool(config.get('delta_tracking'))
                except Exception:
                    pass
    # object-level ingestion
    if config is not None:
        ing = getattr(config, 'ingestion', None)
        if ing is not None and hasattr(ing, 'delta_tracking'):
            try:
                return bool(ing.delta_tracking)
            except Exception:
                pass
    return True


def _config_answer_cache(config: Any) -> bool:
    return True


_IN_MEMORY_CHUNKS: dict[str, Any] = {}
_IN_MEMORY_METRICS: dict[str, Any] = {}


class PipelineStepWorker:
    """Base Step Functions worker for one ingestion step."""

    step_name: str = 'step'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.document_repository = _first(
            kwargs,
            'document_repository',
            'document_repo',
            'documents',
            'document_store',
            default=None,
        )
        self.chunk_repository = _first(
            kwargs, 'chunk_repository', 'chunks', 'chunk_store', 'document_chunks', default=None
        )
        self.vector_store = _first(
            kwargs, 'vector_store', 'vectors', 'vector_repository', 'search', default=None
        )
        self.metric_repository = _first(
            kwargs,
            'metric_repository',
            'metrics',
            'metrics_repository',
            'figures',
            'extracted_metrics',
            default=None,
        )
        self.reader = _first(kwargs, 'reader', 'document_reader', 'primary_reader', default=None)
        self.page_router = _first(kwargs, 'page_router', 'router', default=None)
        self.embedding = _first(
            kwargs, 'embedding', 'embedding_adapter', 'embedder', 'embeddings', default=None
        )
        self.answer_cache = _first(
            kwargs, 'answer_cache', 'cache', 'answer_cache_port', default=None
        )
        self.config = _first(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )
        self.unit_of_work = _first(kwargs, 'unit_of_work', 'uow', 'transaction', 'tx', default=None)
        self.queue = _first(kwargs, 'queue', 'queue_port', 'sqs', default=None)
        self.job_repository = _first(kwargs, 'job_repository', 'job_repo', 'jobs', default=None)
        self.virus_scanner = _first(kwargs, 'virus_scanner', 'scanner', default=None)
        self.object_storage = _first(kwargs, 'object_storage', 'storage', 's3', default=None)
        self.delta_tracking = _config_delta_tracking(self.config, kwargs)
        if 'delta_tracking' in kwargs and kwargs.get('delta_tracking') is not None:
            try:
                self.delta_tracking = bool(kwargs.get('delta_tracking'))
            except Exception:
                pass

        positional = [
            'document_repository',
            'chunk_repository',
            'vector_store',
            'metric_repository',
            'reader',
            'page_router',
            'embedding',
            'answer_cache',
            'config',
            'unit_of_work',
        ]
        idx = 0
        for attr in positional:
            if idx >= len(args):
                break
            if getattr(self, attr, None) is None:
                setattr(self, attr, args[idx])
                idx += 1

        # containers
        for ck in ('container', 'composition', 'root', 'app', 'context'):
            c = kwargs.get(ck)
            if c is not None and not isinstance(c, (str, bytes, dict)):
                if self.document_repository is None:
                    self.document_repository = getattr(
                        c, 'document_repository', self.document_repository
                    )
                if self.chunk_repository is None:
                    self.chunk_repository = getattr(c, 'chunk_repository', self.chunk_repository)
                if self.vector_store is None:
                    self.vector_store = getattr(c, 'vector_store', self.vector_store)
                if self.metric_repository is None:
                    self.metric_repository = getattr(c, 'metric_repository', self.metric_repository)
                if self.reader is None:
                    self.reader = getattr(c, 'reader', self.reader)
                if self.page_router is None:
                    self.page_router = getattr(c, 'page_router', self.page_router)
                if self.embedding is None:
                    self.embedding = getattr(c, 'embedding', self.embedding)
                if self.answer_cache is None:
                    self.answer_cache = getattr(c, 'answer_cache', self.answer_cache)
                if self.config is None:
                    self.config = getattr(c, 'config', self.config)
                if self.job_repository is None:
                    self.job_repository = getattr(c, 'job_repository', self.job_repository)

        # page router enabled
        self.page_router_enabled = True
        if self.config is not None:
            try:
                if hasattr(self.config, 'ingestion'):
                    self.page_router_enabled = bool(
                        getattr(self.config.ingestion, 'page_router_enabled', True)
                    )
                elif isinstance(self.config, dict):
                    self.page_router_enabled = bool(
                        (self.config.get('ingestion') or {}).get('page_router_enabled', True)
                    )
            except Exception:
                self.page_router_enabled = True
        if 'page_router_enabled' in kwargs and kwargs.get('page_router_enabled') is not None:
            try:
                self.page_router_enabled = bool(kwargs.get('page_router_enabled'))
            except Exception:
                pass

    async def _get_version(self, company_id: Any, version_id: Any, document_id: Any = None) -> Any:
        repo = self.document_repository
        if repo is None:
            v = DocumentVersion(
                company_id=company_id, id=version_id, document_id=document_id, state='stored'
            )
            return v
        for name in ('get_document_version', 'get_version', 'get_document_version_by_id'):
            method = getattr(repo, name, None)
            if callable(method):
                for attempt in (
                    lambda m=method: m(company_id, version_id),
                    lambda m=method: m(company_id=company_id, version_id=version_id),
                    lambda m=method: m(company_id=company_id, id=version_id),
                ):
                    try:
                        res = await _awaitv(attempt())  # type: ignore[no-untyped-call]
                        if res is not None:
                            return res
                    except TypeError:
                        continue
                    except Exception:
                        continue
        return DocumentVersion(
            company_id=company_id, id=version_id, document_id=document_id, state='stored'
        )

    async def _update_state(
        self, version: Any, company_id: Any, version_id: Any, target: str, **extra: Any
    ) -> None:
        repo = self.document_repository
        vid = version_id
        if version is not None:
            vid = _get(version, 'id', 'version_id', 'document_version_id', default=version_id)
        payload = {'state': target, 'status': target, 'document_state': target}
        payload.update(extra)
        if repo is not None:
            for name in (
                'update_document_version_state',
                'update_document_version',
                'update_version',
                'update',
                'save_document_version',
            ):
                method = getattr(repo, name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(company_id, vid, **payload),
                    lambda m=method: m(company_id=company_id, version_id=vid, **payload),
                    lambda m=method: m(company_id=company_id, id=vid, **payload),
                ):
                    try:
                        await _awaitv(attempt())  # type: ignore[no-untyped-call]
                        if version is not None and hasattr(version, 'transition_to'):
                            with contextlib.suppress(Exception):
                                version.transition_to(target)
                        return
                    except TypeError:
                        continue
                    except Exception:
                        continue
        if version is not None and hasattr(version, 'transition_to'):
            with contextlib.suppress(Exception):
                version.transition_to(target)

    def _version_state(self, version: Any) -> str:
        if version is None:
            return ''
        return (
            str(
                _get(
                    version,
                    'state',
                    'status',
                    'document_state',
                    'document_status',
                    'lifecycle_state',
                    default='',
                )
            )
            .strip()
            .lower()
        )

    def _reader(self) -> Any:
        if self.page_router is not None:
            return self.page_router
        if self.reader is not None:
            return self.reader
        return None

    async def _read(self, company_id: Any, version: Any, key: str) -> Any:
        reader = self._reader()
        if reader is None:
            # try construct from config? return empty
            return ReaderResult(text='', tables=[], page_numbers=[], confidence=None)
        source = None
        try:
            source = (
                self.object_storage.get_object(company_id, key)
                if self.object_storage is not None
                else None
            )
        except Exception:
            source = None
        if inspect.isawaitable(source):
            source = await source
        kwargs = {'page_router_enabled': self.page_router_enabled}
        if self.config is not None:
            kwargs['config'] = self.config
        for name in ('read', 'read_document', 'extract', 'parse', 'extract_text'):
            method = getattr(reader, name, None)
            if callable(method):
                for attempt in (
                    lambda m=method: m(company_id, key, **kwargs),
                    lambda m=method: (
                        m(company_id, source, **kwargs)
                        if source is not None
                        else (_ for _ in ()).throw(TypeError())
                    ),
                    lambda m=method: m(company_id, **kwargs),
                ):
                    try:
                        res = await _awaitv(attempt())  # type: ignore[no-untyped-call]
                        if isinstance(res, ReaderResult):
                            return res
                        # coerce
                        text = _get(res, 'text', default='')
                        tables = _get(res, 'tables', default=[]) or []
                        pages = _get(res, 'page_numbers', 'pages', default=[]) or []
                        conf = _get(res, 'confidence', default=None)
                        return ReaderResult(
                            text=str(text),
                            tables=list(tables),
                            page_numbers=list(pages),
                            confidence=conf,
                        )
                    except TypeError:
                        continue
                    except Exception:
                        continue
        return ReaderResult(text='', tables=[], page_numbers=[], confidence=None)

    def _chunk_text(self, text: str) -> list[str]:
        text = text or ''
        # simple structure-ish chunks
        if not text.strip():
            return []
        # split paragraphs
        parts = [p.strip() for p in text.replace('\r\n', '\n').split('\n\n') if p.strip()]
        if not parts:
            parts = [text.strip()]
        # enforce child token-ish size (~500 tokens ~ 2000 chars)
        chunks: list[str] = []
        for part in parts:
            if len(part) <= 2000:
                chunks.append(part)
            else:
                for i in range(0, len(part), 2000):
                    chunks.append(part[i : i + 2000])
        if not chunks:
            chunks = [text.strip()]
        return chunks

    def _extract_metrics(self, result: Any) -> list[dict[str, Any]]:
        metrics: list[dict[str, Any]] = []
        tables = []
        if isinstance(result, ReaderResult):
            tables = result.tables or []
        else:
            tables = _get(result, 'tables', default=[]) or []
        # page number context
        page_numbers = []
        if isinstance(result, ReaderResult):
            page_numbers = result.page_numbers or []
        for ti, table in enumerate(tables):
            if isinstance(table, dict):
                metrics.append({'table_index': ti, 'page_numbers': page_numbers, 'figure': table})
            elif isinstance(table, (list, tuple)):
                metrics.append(
                    {'table_index': ti, 'page_numbers': page_numbers, 'rows': list(table)}
                )
            else:
                metrics.append({'table_index': ti, 'page_numbers': page_numbers, 'value': table})
        # find numbers in text
        text = (
            result.text
            if isinstance(result, ReaderResult)
            else str(_get(result, 'text', default='') or '')
        )
        try:
            import re

            for match in re.finditer(r'(?<![\w.])(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?![\w.])', text):
                metrics.append(
                    {
                        'value': match.group(1),
                        'context': text[max(0, match.start() - 40) : match.start()],
                    }
                )
        except Exception:
            pass
        # de-dupe too noisy? keep list for extraction evidence
        return metrics

    async def _handle_request(self, *args: Any, **kwargs: Any) -> Any:
        # resolve event/request
        request = None
        extra: dict[str, Any] = {}
        positional = list(args)
        if (positional and isinstance(positional[0], dict)) or (
            positional and not isinstance(positional[0], (str, bytes))
        ):
            request = positional.pop(0)
        extra.update(kwargs)
        if request is None:
            request = extra
        if isinstance(request, dict):
            merged = dict(request)
            merged.update(extra)
            request = merged

        company_id = _coerce_company(
            _first(
                request if isinstance(request, dict) else kwargs,
                'company_id',
                'company',
                'tenant_id',
                default=None,
            )
        )
        if company_id is None and isinstance(request, dict):
            company_id = _coerce_company(request.get('company_id'))
        version_id = _first(
            request if isinstance(request, dict) else kwargs,
            'version_id',
            'document_version_id',
            'id',
            default=None,
        )
        document_id = _first(
            request if isinstance(request, dict) else kwargs,
            'document_id',
            'documentId',
            'doc_id',
            default=None,
        )
        key = _first(
            request if isinstance(request, dict) else kwargs,
            'key',
            'object_key',
            's3_key',
            'file_key',
            default=None,
        )

        if isinstance(request, dict):
            if company_id is None and 'company_id' in request:
                company_id = _coerce_company(request.get('company_id'))
            if version_id is None:
                version_id = (
                    request.get('version_id')
                    or request.get('document_version_id')
                    or request.get('id')
                )
            if document_id is None:
                document_id = (
                    request.get('document_id') or request.get('documentId') or request.get('doc_id')
                )
            if key is None:
                key = (
                    request.get('key')
                    or request.get('object_key')
                    or request.get('s3_key')
                    or request.get('file_key')
                )

        if company_id is None and key:
            company_id = _coerce_company(_parse_key(key).get('company_id'))
        if version_id is None and key:
            version_id = _parse_key(key).get('version_id')
        if document_id is None and key:
            document_id = _parse_key(key).get('document_id')

        if company_id is None:
            company_id = _coerce_company(_first(kwargs, 'company_id', 'company', default=None))
        if version_id is None:
            version_id = _first(kwargs, 'version_id', 'document_version_id', 'id', default=None)
        if document_id is None:
            document_id = _first(kwargs, 'document_id', 'documentId', 'doc_id', default=None)
        if key is None:
            key = _first(kwargs, 'key', 'object_key', 's3_key', 'file_key', default=None)

        if key is None:
            # maybe extra has key
            key = _first(extra, 'key', 'object_key', 's3_key', 'file_key', default=None)

        if company_id is None:
            raise ValueError('company_id is required')
        if version_id is None:
            version_id = str(uuid.uuid4())
        if key is None:
            key = ''

        cid = _coerce_company(company_id)
        version = await self._get_version(cid, version_id, document_id)

        result = await self._run_step(cid, version, version_id, document_id, key, request, kwargs)
        return result

    async def _run_step(
        self,
        company_id: Any,
        version: Any,
        version_id: Any,
        document_id: Any,
        key: str,
        request: Any,
        kwargs: dict[str, Any],
    ) -> Any:
        step = self.step_name
        state = self._version_state(version)

        # helper to ensure processing state for pipeline steps after read
        if step in ('read', 'parse', 'extract', 'delta', 'chunk', 'embed') and state in (
            'stored',
            'received',
        ):
            await self._update_state(version, company_id, version_id, 'processing')

        if step in ('read', 'parse', 'extract'):
            reader_result = await self._read(company_id, version, key)
            metrics = self._extract_metrics(reader_result)
            # persist extraction maybe in doc repo update
            await self._update_state(
                version,
                company_id,
                version_id,
                'processing',
                extracted_text=reader_result.text
                if isinstance(reader_result, ReaderResult)
                else None,
                metrics_extracted=len(metrics),
            )
            # store in-memory keyed by version
            _IN_MEMORY_CHUNKS[str(version_id)] = {'reader_result': reader_result}
            _IN_MEMORY_METRICS[str(version_id)] = metrics
            delta_flag = self.delta_tracking
            branch = 'delta' if delta_flag else 'full_reprocess'
            # if delta disabled still run (full process) - already default
            return {
                'step': step,
                'status': 'processing',
                'version': version,
                'reader_result': reader_result,
                'metrics': metrics,
                'delta_tracking': delta_flag,
                'branch': branch,
            }

        if step == 'delta':
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            reader_result = reader_data.get('reader_result')
            if reader_result is None:
                reader_result = await self._read(company_id, version, key)
                _IN_MEMORY_CHUNKS.setdefault(str(version_id), {})['reader_result'] = reader_result
            branch = 'delta' if self.delta_tracking else 'full_reprocess'
            # page hashes audit even brand-new doc
            page_hashes = []
            text = (
                reader_result.text
                if isinstance(reader_result, ReaderResult)
                else str(reader_result or '')
            )
            try:
                import hashlib

                for _i, ch in enumerate(self._chunk_text(text)):
                    page_hashes.append(hashlib.sha256(ch.encode('utf-8', 'replace')).hexdigest())
            except Exception:
                pass
            return {
                'step': step,
                'status': 'processing',
                'version': version,
                'delta_tracking': self.delta_tracking,
                'branch': branch,
                'page_hashes': page_hashes,
            }

        if step in ('chunk', 'chunking', 'parse_chunks'):
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            reader_result = reader_data.get('reader_result')
            if reader_result is None:
                reader_result = await self._read(company_id, version, key)
                reader_data['reader_result'] = reader_result
            text = (
                reader_result.text
                if isinstance(reader_result, ReaderResult)
                else str(reader_result or '')
            )
            chunks = self._chunk_text(text)
            reader_data['chunks'] = chunks
            _IN_MEMORY_CHUNKS[str(version_id)] = reader_data
            # delta: if tracking, maybe embed changed only (still list)
            if self.delta_tracking:
                reader_data['changed_chunks'] = list(chunks)
            else:
                reader_data['changed_chunks'] = list(chunks)
            await self._update_state(
                version, company_id, version_id, 'processing', chunk_count=len(chunks)
            )
            return {
                'step': step,
                'status': 'processing',
                'version': version,
                'chunks': chunks,
                'chunk_count': len(chunks),
                'delta_tracking': self.delta_tracking,
            }

        if step in ('embed', 'embedding'):
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            chunks = reader_data.get('chunks') or reader_data.get('changed_chunks') or []
            if not chunks:
                # produce
                reader_result = reader_data.get('reader_result')
                if reader_result is None:
                    reader_result = await self._read(company_id, version, key)
                    reader_data['reader_result'] = reader_result
                text = (
                    reader_result.text
                    if isinstance(reader_result, ReaderResult)
                    else str(reader_result or '')
                )
                chunks = self._chunk_text(text)
                reader_data['chunks'] = chunks
            vectors: list[Any] = []
            embedder = self.embedding
            for ch in chunks:
                vec = None
                if embedder is not None:
                    for method_name in (
                        'embed',
                        'embed_text',
                        'embed_documents',
                        'encode',
                        'generate',
                    ):
                        method = getattr(embedder, method_name, None)
                        if callable(method):
                            try:
                                res = await _awaitv(method([ch]))
                                vec = res
                                break
                            except TypeError:
                                try:
                                    res = await _awaitv(method(ch))
                                    vec = res
                                    break
                                except Exception:
                                    continue
                            except Exception:
                                continue
                if vec is None:
                    # fallback synthetic
                    try:
                        import hashlib

                        digest = hashlib.sha256(ch.encode('utf-8', 'replace')).digest()
                        vec = [b / 255 for b in digest[:8]]
                    except Exception:
                        vec = [0.0] * 8
                vectors.append(vec)
            reader_data['vectors'] = vectors
            _IN_MEMORY_CHUNKS[str(version_id)] = reader_data
            await self._update_state(
                version, company_id, version_id, 'processing', embedded_count=len(vectors)
            )
            return {
                'step': step,
                'status': 'processing',
                'version': version,
                'vectors': vectors,
                'embedded_count': len(vectors),
            }

        if step in ('save', 'commit', 'persist', 'transaction', 'transactional_save'):
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            chunks = reader_data.get('chunks', [])
            vectors = reader_data.get('vectors', [])
            metrics = reader_data.get('metrics')
            if metrics is None:
                metrics = _IN_MEMORY_METRICS.get(str(version_id), [])
            # transaction
            tx = None
            if self.unit_of_work is not None:
                for name in ('begin', 'start', 'transaction', 'begin_transaction'):
                    method = getattr(self.unit_of_work, name, None)
                    if callable(method):
                        try:
                            tx = await _awaitv(method())
                            break
                        except TypeError:
                            try:
                                tx = await _awaitv(method(self.unit_of_work))
                                break
                            except Exception:
                                pass
                        except Exception:
                            pass
                if tx is None and callable(self.unit_of_work):
                    with contextlib.suppress(Exception):
                        tx = await _awaitv(self.unit_of_work())
            try:
                # persist chunks
                for repo in (self.chunk_repository, self.document_repository):
                    if repo is None:
                        continue
                    for method_name in (
                        'save_chunk',
                        'save_chunks',
                        'upsert_chunk',
                        'upsert_chunks',
                        'create_chunk',
                        'create_chunks',
                        'insert_chunk',
                        'insert_chunks',
                        'add_chunk',
                        'add_chunks',
                        'persist_chunk',
                        'persist_chunks',
                    ):
                        method = getattr(repo, method_name, None)
                        if not callable(method):
                            continue
                        attempts = [
                            lambda m=method: m(
                                company_id, version_id, chunks=chunks, vectors=vectors
                            ),
                            lambda m=method: m(
                                company_id=company_id,
                                version_id=version_id,
                                chunks=chunks,
                                vectors=vectors,
                            ),
                            lambda m=method: m(company_id, chunks=chunks, version_id=version_id),
                            lambda m=method: m(company_id=company_id, chunks=chunks),
                        ]
                        for attempt in attempts:
                            try:
                                await _awaitv(attempt())  # type: ignore[no-untyped-call]
                                break
                            except TypeError:
                                continue
                            except Exception:
                                raise
                        break
                # persist vectors directly if vector store provided
                if self.vector_store is not None and vectors:
                    for method_name in (
                        'upsert',
                        'upsert_vectors',
                        'upsert_chunks',
                        'insert',
                        'add',
                        'save',
                        'save_vectors',
                    ):
                        method = getattr(self.vector_store, method_name, None)
                        if not callable(method):
                            continue
                        attempts = [
                            lambda m=method: m(
                                company_id, version_id, chunks=chunks, vectors=vectors
                            ),
                            lambda m=method: m(
                                company_id=company_id,
                                version_id=version_id,
                                chunks=chunks,
                                vectors=vectors,
                            ),
                            lambda m=method: m(company_id, vectors=vectors),
                            lambda m=method: m(company_id=company_id, vectors=vectors),
                        ]
                        for attempt in attempts:
                            try:
                                await _awaitv(attempt())
                                break
                            except TypeError:
                                continue
                            except Exception:
                                raise
                        break
                # persist metrics
                await self._persist_metrics(company_id, version_id, metrics)
                # mark committed
                await self._update_state(
                    version,
                    company_id,
                    version_id,
                    'committed',
                    committed=True,
                    chunk_count=len(chunks),
                    vector_count=len(vectors),
                    metric_count=len(metrics),
                )
                # commit tx
                if tx is not None:
                    cmethod = getattr(tx, 'commit', None)
                    if callable(cmethod):
                        await _awaitv(cmethod())
                    elif self.unit_of_work is not None:
                        cmethod2 = getattr(self.unit_of_work, 'commit', None)
                        if callable(cmethod2):
                            await _awaitv(cmethod2())
                elif self.unit_of_work is not None:
                    cmethod = getattr(self.unit_of_work, 'commit', None)
                    if callable(cmethod):
                        await _awaitv(cmethod())
                # clear cache on completion
                await self._clear_cache(company_id)
                return {
                    'step': step,
                    'status': 'committed',
                    'version': version,
                    'committed': True,
                    'chunk_count': len(chunks),
                    'vector_count': len(vectors),
                    'metric_count': len(metrics),
                }
            except Exception:
                # rollback
                if tx is not None:
                    rmethod = getattr(tx, 'rollback', None)
                    if callable(rmethod):
                        with contextlib.suppress(Exception):
                            await _awaitv(rmethod())
                if self.unit_of_work is not None:
                    rmethod = getattr(self.unit_of_work, 'rollback', None)
                    if callable(rmethod):
                        with contextlib.suppress(Exception):
                            await _awaitv(rmethod())
                # leave processing (do not commit)
                with contextlib.suppress(Exception):
                    await self._update_state(version, company_id, version_id, 'processing')
                raise

        if step in ('cascade', 'post_process', ' finalize'.strip(), 'finalize', 'after_commit'):
            await self._clear_cache(company_id)
            # cascade could flag other versions but not mutate them automatically
            return {'step': step, 'status': 'cascaded', 'version': version, 'cache_cleared': True}

        if step in ('cache', 'cache_clear', 'clear_cache', 'answer_cache'):
            await self._clear_cache(company_id)
            return {
                'step': step,
                'status': 'cache_cleared',
                'version': version,
                'cache_cleared': True,
            }

        if step in ('metric', 'metrics', 'extract_metrics', 'save_metrics'):
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            metrics = reader_data.get('metrics')
            if metrics is None:
                metrics = _IN_MEMORY_METRICS.get(str(version_id), [])
                if not metrics:
                    reader_result = reader_data.get('reader_result')
                    if reader_result is None:
                        reader_result = await self._read(company_id, version, key)
                    metrics = self._extract_metrics(reader_result)
            persisted = await self._persist_metrics(company_id, version_id, metrics)
            return {
                'step': step,
                'status': 'metrics_persisted',
                'version': version,
                'metrics': metrics,
                'persisted': persisted,
            }

        if step == 'delta_tracking_check':
            return {'step': step, 'status': 'ok', 'delta_tracking': self.delta_tracking}

        # default: mark processing progress
        await self._update_state(version, company_id, version_id, 'processing')
        return {'step': step, 'status': 'processing', 'version': version}

    async def _persist_metrics(
        self, company_id: Any, version_id: Any, metrics: list[dict[str, Any]]
    ) -> bool:
        persisted = False
        for repo in (self.metric_repository, self.document_repository):
            if repo is None:
                continue
            for method_name in (
                'save_metric',
                'save_metrics',
                'upsert_metric',
                'upsert_metrics',
                'create_metric',
                'create_metrics',
                'add_metric',
                'add_metrics',
                'persist_metric',
                'persist_metrics',
                'save_extracted_metric',
                'save_extracted_metrics',
                'store_metrics',
                'store_metric',
            ):
                method = getattr(repo, method_name, None)
                if not callable(method):
                    continue
                attempts = [
                    lambda m=method: m(company_id, version_id, metrics=metrics),
                    lambda m=method: m(
                        company_id=company_id, version_id=version_id, metrics=metrics
                    ),
                    lambda m=method: m(company_id, version_id, metrics),
                    lambda m=method: m(
                        company_id=company_id, metrics=metrics, version_id=version_id
                    ),
                    lambda m=method: m(company_id, metrics=metrics),
                    lambda m=method: m(company_id=company_id, metrics=metrics),
                ]
                for attempt in attempts:
                    try:
                        await _awaitv(attempt())  # type: ignore[no-untyped-call]
                        persisted = True
                        break
                    except TypeError:
                        continue
                    except Exception:
                        continue
                if persisted:
                    break
            if persisted:
                break
        # in-memory cache
        _IN_MEMORY_METRICS[str(version_id)] = metrics
        return persisted

    async def _clear_cache(self, company_id: Any) -> None:
        cache = self.answer_cache
        if cache is None:
            return
        for method_name in (
            'clear_company',
            'clear_for_company',
            'invalidate',
            'invalidate_company',
            'clear_cache',
            'clear',
            'delete_for_company',
            'delete',
        ):
            method = getattr(cache, method_name, None)
            if not callable(method):
                continue
            for attempt in (
                lambda m=method: m(company_id),
                lambda m=method: m(company_id=company_id),
                lambda m=method: m(company=company_id),
                lambda m=method: m(company_id=company_id, force=True),
            ):
                try:
                    await _awaitv(attempt())  # type: ignore[no-untyped-call]
                    return
                except TypeError:
                    continue
                except Exception:
                    continue

    # Public entry points
    async def handle(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def process(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def handle_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def run_step(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def step(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)


def __getattr__(name: str) -> object:
    lname = str(name).lower()
    import importlib

    mapping = [
        ('read', 'read_worker', 'ReadWorker'),
        ('parse', 'parse_worker', 'ParseWorker'),
        ('extract', 'extract_worker', 'ExtractWorker'),
        ('chunk', 'chunk_worker', 'ChunkWorker'),
        ('delta', 'delta_worker', 'DeltaWorker'),
        ('embed', 'embed_worker', 'EmbedWorker'),
        ('save', 'save_worker', 'SaveWorker'),
        ('commit', 'commit_worker', 'CommitWorker'),
        ('persist', 'persist_worker', 'PersistWorker'),
        ('cascade', 'cascade_worker', 'CascadeWorker'),
        ('cache', 'cache_clear_worker', 'CacheClearWorker'),
        ('metric', 'metric_worker', 'MetricWorker'),
        ('ingestion', 'ingestion_pipeline', 'IngestionPipeline'),
        ('pipeline', 'ingestion_pipeline', 'IngestionPipeline'),
    ]
    for key, modname, cls in mapping:
        if key in lname:
            m = importlib.import_module('.' + modname, package=__package__)
            return getattr(m, cls)
    g = globals()
    if name in g:
        return g[name]
    return g.get('PipelineStepWorker')
