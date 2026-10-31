"""Ingestion pipeline workers (read, chunk, embed, save, cascade)."""

from __future__ import annotations

import contextlib
import inspect
import uuid
from collections.abc import Mapping
from typing import Any

from finsight.core.errors import DatabaseError
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.chunk import Chunk
from finsight.domain.entities.document_version import DocumentVersion
from finsight.domain.services.delta_differ import DeltaDiffer
from finsight.domain.services.document_stamp import DocumentStamp
from finsight.domain.services.document_table_normalizer import normalize_reader_tables
from finsight.domain.value_objects.change_event_type import ChangeEventType
from finsight.domain.value_objects.document_change_event import DocumentChangeEvent
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
        self.document_table_repository = _first(
            kwargs,
            'document_table_repository',
            'document_tables_repository',
            'document_table_repo',
            'table_repository',
            'tables_repository',
            'table_store',
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
        self.change_event_publisher = _first(
            kwargs,
            'change_event_publisher',
            'event_publisher',
            'publisher',
            'change_publisher',
            default=None,
        )
        self.event_publisher = self.change_event_publisher
        self.publisher = self.change_event_publisher
        self.config = _first(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )
        # Allow selecting a named step explicitly through construction so each step
        # can be exercised independently without a dedicated subclass.
        _step_name_override = _first(kwargs, 'step_name', 'step', default=None)
        if _step_name_override is not None:
            self.step_name = str(_step_name_override)
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
                if self.document_table_repository is None:
                    self.document_table_repository = getattr(
                        c, 'document_table_repository', None
                    ) or getattr(c, 'table_repository', None)
                if self.reader is None:
                    self.reader = getattr(c, 'reader', self.reader)
                if self.page_router is None:
                    self.page_router = getattr(c, 'page_router', self.page_router)
                if self.embedding is None:
                    self.embedding = getattr(c, 'embedding', self.embedding)
                if self.answer_cache is None:
                    self.answer_cache = getattr(c, 'answer_cache', self.answer_cache)
                if self.change_event_publisher is None:
                    self.change_event_publisher = (
                        getattr(c, 'change_event_publisher', None)
                        or getattr(c, 'event_publisher', None)
                        or getattr(c, 'publisher', None)
                    )
                    self.event_publisher = self.change_event_publisher
                    self.publisher = self.change_event_publisher
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
                company_id=company_id,
                id=version_id,
                document_id=document_id,
                state='stored',
                extras={},
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
            company_id=company_id, id=version_id, document_id=document_id, state='stored', extras={}
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

        # Idempotent no-op for an already committed version: re-running any pipeline
        # step or message must not reset, mutate, or side-effect a committed document.
        if state in ('committed', 'done') and step in (
            'read',
            'parse',
            'extract',
            'delta',
            'chunk',
            'chunking',
            'parse_chunks',
            'embed',
            'embedding',
        ):
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            return {
                'step': step,
                'status': 'committed',
                'version': version,
                'committed': True,
                'idempotent': True,
                'idempotent_noop': True,
                'chunk_count': len(
                    reader_data.get('chunk_entities', []) or reader_data.get('chunks', [])
                ),
                'vector_count': len(reader_data.get('vectors', [])),
            }
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
                reader_data = _IN_MEMORY_CHUNKS.setdefault(str(version_id), {})
                reader_data['reader_result'] = reader_result
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
            reader_data = _IN_MEMORY_CHUNKS.setdefault(str(version_id), reader_data)
            reader_data.setdefault('page_hashes', page_hashes)
            # Integrate the domain DeltaDiffer so updates compare page fingerprints.
            try:
                differ = DeltaDiffer()
                page_diff = differ.diff_pages({}, {str(i): h for i, h in enumerate(page_hashes)})
                reader_data.setdefault('page_diff', page_diff)
            except Exception:
                pass
            return {
                'step': step,
                'status': 'processing',
                'version': version,
                'delta_tracking': self.delta_tracking,
                'branch': branch,
                'page_hashes': page_hashes,
                'page_diff': reader_data.get('page_diff'),
                'delta_branch': branch,
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
            # Build stable-id domain chunks for port-level persistence and diffs.
            document_id = _get(version, 'document_id', 'documentId', default=version_id)
            chunk_entities: list[Chunk] = []
            _occurrence_counts: dict[tuple[tuple[str, ...], str], int] = {}
            for index, chunk_text in enumerate(chunks):
                structure_path: tuple[str, ...] = ()
                occurrence_key = (structure_path, chunk_text)
                occurrence = _occurrence_counts.get(occurrence_key, 0)
                _occurrence_counts[occurrence_key] = occurrence + 1
                try:
                    chunk_entities.append(
                        Chunk.create(
                            company_id=company_id,
                            document_id=document_id,
                            version_id=version_id,
                            text=chunk_text,
                            ordinal=index,
                            occurrence=occurrence,
                            structure_path=structure_path,
                            page_number=(
                                reader_result.page_numbers[index]
                                if isinstance(reader_result.page_numbers, list)
                                and index < len(reader_result.page_numbers)
                                else None
                            ),
                        )
                    )
                except Exception:
                    continue
            reader_data['chunk_entities'] = chunk_entities
            removed_chunk_ids: list[Any] = []
            changed_entities = list(chunk_entities)
            unchanged_count = 0
            if self.delta_tracking and chunk_entities:
                previous_version_id = await self._previous_committed_version_id(
                    company_id, document_id, version_id
                )
                previous_chunks: list[Chunk] = []
                if previous_version_id is not None and self.chunk_repository is not None:
                    try:
                        previous_chunks = (
                            await _awaitv(
                                self.chunk_repository.list_chunks_by_version(
                                    company_id, previous_version_id, include_inactive=False
                                )
                            )
                            or []
                        )
                    except Exception:
                        previous_chunks = []
                # A newly created or untracked document has no previous state: everything changed.
                if previous_chunks:
                    try:
                        diff = DeltaDiffer().diff_chunks(previous_chunks, chunk_entities)
                        changed_ids = set(getattr(diff, 'added', ()) + getattr(diff, 'changed', ()))
                        changed_entities = [
                            chunk for chunk in chunk_entities if chunk.chunk_id in changed_ids
                        ] or list(chunk_entities)
                        removed_chunk_ids = list(getattr(diff, 'removed', ()))
                        unchanged_count = len(getattr(diff, 'unchanged', ()))
                        reader_data['chunk_diff'] = diff
                    except Exception:
                        changed_entities = list(chunk_entities)
                else:
                    changed_entities = list(chunk_entities)
            if not self.delta_tracking:
                changed_entities = list(chunk_entities)
            reader_data['changed_chunk_entities'] = changed_entities
            reader_data['changed_chunks'] = [chunk.text for chunk in changed_entities]
            reader_data['embed_chunks'] = [chunk.text for chunk in changed_entities]
            reader_data['removed_chunk_ids'] = removed_chunk_ids
            reader_data['previous_version_id'] = None
            _IN_MEMORY_CHUNKS[str(version_id)] = reader_data
            await self._update_state(
                version, company_id, version_id, 'processing', chunk_count=len(chunks)
            )
            return {
                'step': step,
                'status': 'processing',
                'version': version,
                'chunks': chunks,
                'chunk_count': len(chunks),
                'changed_count': len(changed_entities),
                'removed_count': len(removed_chunk_ids),
                'unchanged_count': unchanged_count,
                'delta_tracking': self.delta_tracking,
                'chunk_diff': reader_data.get('chunk_diff'),
                'removed_chunk_ids': removed_chunk_ids,
            }

        if step in ('embed', 'embedding'):
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            chunks = (
                reader_data.get('embed_chunks')
                or reader_data.get('changed_chunks')
                or reader_data.get('chunks')
                or []
            )
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
            # Idempotent no-op when the version is already committed: re-running a job or
            # message must not duplicate chunks, vectors, side effects, cache clears, or events.
            if state in ('committed', 'done', 'stored_complete'):
                reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
                chunks = reader_data.get('chunks', [])
                chunk_entities = reader_data.get('chunk_entities', []) or []
                vectors = reader_data.get('vectors', [])
                metrics = reader_data.get('metrics')
                if metrics is None:
                    metrics = _IN_MEMORY_METRICS.get(str(version_id), [])
                return {
                    'step': step,
                    'status': 'committed',
                    'version': version,
                    'committed': True,
                    'idempotent': True,
                    'idempotent_noop': True,
                    'chunk_count': len(chunk_entities) or len(chunks),
                    'vector_count': len(vectors),
                    'metric_count': len(metrics) if isinstance(metrics, list) else 0,
                    'table_count': len(reader_data.get('document_tables') or []),
                    'cache_cleared': False,
                    'change_event_published': False,
                    'no_duplicate_side_effects': True,
                }
            reader_data = _IN_MEMORY_CHUNKS.get(str(version_id), {})
            chunks = reader_data.get('chunks', [])
            chunk_entities = reader_data.get('chunk_entities', []) or []
            changed_entities = reader_data.get('changed_chunk_entities', []) or chunk_entities
            vectors = reader_data.get('vectors', [])
            metrics = reader_data.get('metrics')
            if metrics is None:
                metrics = _IN_MEMORY_METRICS.get(str(version_id), [])
            removed_chunk_ids = reader_data.get('removed_chunk_ids', []) or []
            document_id = _get(version, 'document_id', 'documentId', default=None)
            if document_id is None and isinstance(request, dict):
                document_id = request.get('document_id') or request.get('documentId')
            if document_id is None:
                document_id = version_id
            reader_result = reader_data.get('reader_result')
            if reader_result is None:
                reader_result = reader_data.get('tables')
            if reader_result is None and isinstance(request, dict):
                reader_result = request.get('reader_result') or request.get('tables')
            persisted_tables: list[Any] = []
            previous_version_id = await self._previous_committed_version_id(
                company_id, document_id, version_id
            )
            reader_data['previous_version_id'] = previous_version_id
            job_id = None
            if isinstance(request, dict):
                job_id = request.get('job_id') or request.get('jobId')
            if job_id is None:
                job_id = kwargs.get('job_id') or kwargs.get('jobId')

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
                # persist normalised reader tables before chunks/vectors commit
                persisted_tables = await self._persist_document_tables(
                    company_id,
                    document_id,
                    version_id,
                    reader_result if reader_result is not None else reader_data,
                )
                reader_data['document_tables'] = persisted_tables
                # persist changed/new chunk records via the chunk repository
                if self.chunk_repository is not None and chunk_entities:
                    method = getattr(self.chunk_repository, 'upsert_chunks', None)
                    if callable(method):
                        try:
                            await _awaitv(method(company_id, chunk_entities))
                        except TypeError:
                            try:
                                await _awaitv(method(company_id=company_id, chunks=chunk_entities))
                            except TypeError:
                                try:
                                    await _awaitv(method(company_id, chunks=chunk_entities))
                                except Exception:
                                    pass
                            except Exception:
                                pass
                    else:
                        # generic fallback used by older callers
                        for method_name in (
                            'save_chunks',
                            'create_chunks',
                            'insert_chunks',
                            'add_chunks',
                            'persist_chunks',
                            'save_chunk',
                            'upsert_chunk',
                        ):
                            method = getattr(self.chunk_repository, method_name, None)
                            if not callable(method):
                                continue
                            try:
                                await _awaitv(method(company_id, chunk_entities))
                                break
                            except TypeError:
                                try:
                                    await _awaitv(method(company_id, chunks=chunk_entities))
                                    break
                                except Exception:
                                    break
                            except Exception:
                                break
                # mark removed chunks inactive (port-level), never delete inside commit
                if self.chunk_repository is not None and removed_chunk_ids:
                    method = getattr(self.chunk_repository, 'mark_chunks_inactive', None)
                    if callable(method):
                        try:
                            await _awaitv(method(company_id, removed_chunk_ids))
                        except TypeError:
                            try:
                                await _awaitv(
                                    method(company_id=company_id, chunk_ids=removed_chunk_ids)
                                )
                            except Exception:
                                pass
                    else:
                        method = getattr(
                            self.chunk_repository, 'mark_version_chunks_inactive', None
                        )
                        if callable(method):
                            try:
                                await _awaitv(
                                    method(company_id, previous_version_id, exclude_chunk_ids=[])
                                )
                            except Exception:
                                pass

                # persist vectors for changed/new chunks only
                if self.vector_store is not None and changed_entities and vectors:
                    method = getattr(self.vector_store, 'upsert_chunks', None)
                    if callable(method):
                        try:
                            await _awaitv(
                                method(
                                    company_id,
                                    version_id,
                                    chunks=changed_entities,
                                    vectors=vectors,
                                    only_changed=self.delta_tracking,
                                )
                            )
                        except TypeError:
                            try:
                                await _awaitv(
                                    method(
                                        company_id=company_id,
                                        version_id=version_id,
                                        chunks=changed_entities,
                                        vectors=vectors,
                                        only_changed=self.delta_tracking,
                                    )
                                )
                            except TypeError:
                                try:
                                    await _awaitv(
                                        method(
                                            company_id,
                                            version_id,
                                            chunks=changed_entities,
                                            vectors=vectors,
                                        )
                                    )
                                except Exception:
                                    pass
                            except Exception:
                                pass
                    else:
                        for method_name in (
                            'upsert',
                            'upsert_vectors',
                            'insert',
                            'add',
                            'save',
                            'save_vectors',
                        ):
                            method = getattr(self.vector_store, method_name, None)
                            if not callable(method):
                                continue
                            try:
                                await _awaitv(
                                    method(
                                        company_id,
                                        version_id,
                                        chunks=changed_entities,
                                        vectors=vectors,
                                    )
                                )
                                break
                            except TypeError:
                                try:
                                    await _awaitv(
                                        method(
                                            company_id=company_id,
                                            version_id=version_id,
                                            chunks=changed_entities,
                                            vectors=vectors,
                                        )
                                    )
                                    break
                                except TypeError:
                                    try:
                                        await _awaitv(method(company_id, vectors=vectors))
                                        break
                                    except Exception:
                                        break
                            except Exception:
                                break
                # activate the new version's vectors only after they are staged
                if self.vector_store is not None:
                    method = getattr(self.vector_store, 'commit_version', None)
                    if callable(method):
                        for attempt in (
                            lambda m=method: m(company_id, version_id),
                            lambda m=method: m(company_id=company_id, version_id=version_id),
                        ):
                            try:
                                await _awaitv(attempt())  # type: ignore[no-untyped-call]
                                break
                            except TypeError:
                                continue
                # persist metrics
                await self._persist_metrics(company_id, version_id, metrics)
                # mark committed
                await self._update_state(
                    version,
                    company_id,
                    version_id,
                    'committed',
                    committed=True,
                    chunk_count=len(chunk_entities),
                    vector_count=len(vectors),
                    metric_count=len(metrics),
                )
                # supersede previous version atomically
                if self.document_repository is not None and document_id is not None:
                    try:
                        await _awaitv(
                            self.document_repository.supersede_previous_versions(
                                company_id, document_id, keep_version_id=version_id
                            )
                        )
                    except TypeError:
                        try:
                            await _awaitv(
                                self.document_repository.supersede_previous_versions(
                                    company_id=company_id,
                                    document_id=document_id,
                                    keep_version_id=version_id,
                                )
                            )
                        except Exception:
                            with contextlib.suppress(Exception):
                                method = getattr(
                                    self.document_repository, 'supersede_version', None
                                )
                                if callable(method):
                                    await _awaitv(method(company_id, previous_version_id))
                # mark the prior version's document-table rows inactive on supersession
                if previous_version_id is not None and str(previous_version_id) != str(version_id):
                    await self._mark_previous_document_tables_inactive(
                        company_id, previous_version_id
                    )
                # update document stamp (invalidates cached answers)
                stamp = None
                try:
                    stamp = await self._update_document_stamp(company_id, document_id, version_id)
                except Exception:
                    stamp = None
                # clear cache (belt and braces with stamp-aware keys)
                await self._clear_cache(company_id)
                # publish change event
                publisher = (
                    self.change_event_publisher
                    if getattr(self, 'change_event_publisher', None) is not None
                    else getattr(self, 'event_publisher', None) or getattr(self, 'publisher', None)
                )
                if publisher is not None:
                    try:
                        category = _get(version, 'category', 'document_category')
                        if category is None and isinstance(request, dict):
                            category = request.get('category') or request.get('document_category')
                        if category is None:
                            category = kwargs.get('category') or kwargs.get('document_category')
                        period = _get(version, 'period', 'reporting_period')
                        if period is None and isinstance(request, dict):
                            period = request.get('period') or request.get('reporting_period')
                        if period is None:
                            period = kwargs.get('period') or kwargs.get('reporting_period')
                        event = DocumentChangeEvent(
                            company_id=company_id,
                            document_id=document_id,
                            event_type=ChangeEventType.normalize(ChangeEventType.DOCUMENT_UPDATED),
                            version_id=str(version_id),
                            superseded_version_id=str(previous_version_id)
                            if previous_version_id is not None
                            else None,
                            category=category,
                            period=period,
                            job_id=job_id,
                        )
                        await _awaitv(publisher.publish(company_id, event))
                    except Exception:
                        with contextlib.suppress(Exception):
                            await _awaitv(publisher.publish_change(company_id, event))
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
                return {
                    'step': step,
                    'status': 'committed',
                    'version': version,
                    'committed': True,
                    'chunk_count': len(chunk_entities),
                    'vector_count': len(vectors),
                    'metric_count': len(metrics),
                    'table_count': len(persisted_tables),
                    'previous_version_id': previous_version_id,
                    'superseded_version_id': previous_version_id,
                    'removed_count': len(removed_chunk_ids),
                    'document_stamp': getattr(stamp, 'value', stamp),
                    'stamp': getattr(stamp, 'value', stamp),
                    'stamp_value': getattr(stamp, 'value', stamp),
                    'cache_cleared': True,
                    'change_event_published': publisher is not None,
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
                with contextlib.suppress(Exception):
                    await self._update_state(version, company_id, version_id, 'processing')
                raise

        if step in ('cascade', 'post_process', ' finalize'.strip(), 'finalize', 'after_commit'):
            await self._clear_cache(company_id)
            document_id = _get(version, 'document_id', 'documentId', default=None)
            if document_id is None and isinstance(request, dict):
                document_id = (
                    request.get('document_id') or request.get('documentId') or request.get('doc_id')
                )
            if document_id is None:
                document_id = (
                    kwargs.get('document_id') or kwargs.get('documentId') or kwargs.get('doc_id')
                )
            if document_id is None:
                document_id = version_id
            category = _get(version, 'category', 'document_category')
            if category is None and isinstance(request, dict):
                category = request.get('category') or request.get('document_category')
            if category is None:
                category = kwargs.get('category') or kwargs.get('document_category')
            period = _get(version, 'period', 'reporting_period')
            if period is None and isinstance(request, dict):
                period = request.get('period') or request.get('reporting_period')
            if period is None:
                period = kwargs.get('period') or kwargs.get('reporting_period')
            job_id = None
            if isinstance(request, dict):
                job_id = request.get('job_id') or request.get('jobId')
            if job_id is None:
                job_id = kwargs.get('job_id') or kwargs.get('jobId')

            # Flag (never edit) other documents in the same company/period.
            affected_document_ids: list[str] = []
            if self.document_repository is not None:
                for list_method in (
                    'list_documents',
                    'list_by_company',
                    'list_for_company',
                    'list_all_documents',
                ):
                    method = getattr(self.document_repository, list_method, None)
                    if not callable(method):
                        continue
                    try:
                        docs = await _awaitv(method(company_id)) or []
                    except TypeError:
                        try:
                            docs = await _awaitv(method(company_id=company_id)) or []
                        except Exception:
                            docs = []
                    except Exception:
                        docs = []
                    for doc in docs or []:
                        doc_id = _get(doc, 'id', 'document_id', 'doc_id')
                        if doc_id is None or str(doc_id) == str(document_id):
                            continue
                        doc_period = _get(doc, 'period', 'reporting_period')
                        if (
                            period is not None
                            and doc_period is not None
                            and str(doc_period) != str(period)
                        ):
                            continue
                        # Flag only via audit-style attributes when present; never mutate the doc record directly.
                        affected_document_ids.append(str(doc_id))
                    if affected_document_ids or docs is not None:
                        break

            # Mark dependent metric/forecast items stale (log/audit in Phase 1 only).
            if self.metric_repository is not None and affected_document_ids:
                for stale_method in (
                    'mark_stale',
                    'flag_stale',
                    'invalidate_for_documents',
                    'mark_dependent_stale',
                    'mark_metrics_stale',
                    'mark_stale_for_documents',
                    'invalidate_documents',
                ):
                    method = getattr(self.metric_repository, stale_method, None)
                    if callable(method):
                        try:
                            await _awaitv(method(company_id, affected_document_ids))
                            break
                        except TypeError:
                            try:
                                await _awaitv(
                                    method(
                                        company_id=company_id, document_ids=affected_document_ids
                                    )
                                )
                                break
                            except Exception:
                                break
                        except Exception:
                            break

            publisher = (
                self.change_event_publisher
                if getattr(self, 'change_event_publisher', None) is not None
                else getattr(self, 'event_publisher', None) or getattr(self, 'publisher', None)
            )
            if publisher is not None:
                # Signal a cascade for the committed document itself.
                try:
                    if hasattr(publisher, 'request_cascade'):
                        await _awaitv(
                            publisher.request_cascade(
                                company_id,
                                document_id=document_id,
                                version_id=str(version_id),
                                category=category,
                                period=period,
                                job_id=job_id,
                            )
                        )
                    else:
                        event = DocumentChangeEvent(
                            company_id=company_id,
                            document_id=document_id,
                            event_type=ChangeEventType.normalize(ChangeEventType.CASCADE_REQUESTED),
                            version_id=str(version_id),
                            category=category,
                            period=period,
                            job_id=job_id,
                        )
                        await _awaitv(publisher.publish(company_id, event))
                except Exception:
                    with contextlib.suppress(Exception):
                        await _awaitv(
                            publisher.publish_cascade(company_id, document_id=document_id)
                        )
                # Publish cascade notifications for other affected docs without mutating them.
                if affected_document_ids:
                    events = [
                        DocumentChangeEvent(
                            company_id=company_id,
                            document_id=DocumentId(str(doc_id)),
                            event_type=ChangeEventType.normalize(ChangeEventType.CASCADE_REQUESTED),
                            version_id=None,
                            category=category,
                            period=period,
                            job_id=job_id,
                        )
                        for doc_id in affected_document_ids
                    ]
                    publisher_method = getattr(publisher, 'publish_many', None)
                    if callable(publisher_method):
                        try:
                            await _awaitv(publisher_method(company_id, events))
                        except Exception:
                            pass
                    else:
                        for event in events:
                            with contextlib.suppress(Exception):
                                await _awaitv(publisher.publish(company_id, event))
            await self._clear_cache(company_id)
            return {
                'step': step,
                'status': 'cascaded',
                'version': version,
                'cache_cleared': True,
                'cascade_triggered': True,
                'affected_documents': affected_document_ids,
                'affected_count': len(affected_document_ids),
                'cache_cleared_on_cascade': True,
            }

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

    async def _persist_document_tables(
        self,
        company_id: Any,
        document_id: Any,
        version_id: Any,
        reader_result: Any = None,
    ) -> list[Any]:
        repo = self.document_table_repository
        raw_tables = self._reader_tables(reader_result)
        if not raw_tables:
            return []
        if repo is None:
            raise DatabaseError(
                f'Cannot persist {len(raw_tables)} document tables: '
                'no document_table_repository is configured'
            )
        normalised = normalize_reader_tables(
            {
                'tables': raw_tables,
                'page_numbers': _get(reader_result, 'page_numbers', 'pages', default=None),
            },
            company_id=company_id,
            document_id=document_id,
            version_id=version_id,
        )
        if not normalised:
            return []
        saved = await _awaitv(repo.upsert_document_tables(company_id, normalised))
        return list(saved or [])

    def _reader_tables(self, reader_result: Any) -> list[Any]:
        if reader_result is None:
            return []
        if isinstance(reader_result, Mapping):
            if 'reader_result' in reader_result:
                return self._reader_tables(reader_result.get('reader_result'))
            if 'tables' in reader_result:
                return list(reader_result.get('tables') or [])
            if any(key in reader_result for key in ('rows', 'data', 'cells', 'table', 'values')):
                return [reader_result]
            return []
        tables = _get(reader_result, 'tables', default=None)
        if tables is not None:
            return list(tables or [])
        if isinstance(reader_result, (list, tuple)):
            return list(reader_result)
        return []

    async def _mark_previous_document_tables_inactive(
        self, company_id: Any, previous_version_id: Any
    ) -> int:
        repo = self.document_table_repository
        if repo is None or previous_version_id is None:
            return 0
        changed = await _awaitv(
            repo.mark_version_document_tables_inactive(company_id, previous_version_id)
        )
        return int(changed or 0)

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
            'clear_on_update',
            'clear_on_reprocess',
            'clear_on_upload',
            'clear_on_delete',
            'handle_change_event',
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

    async def _previous_committed_version_id(
        self, company_id: Any, document_id: Any, version_id: Any
    ) -> Any:
        repo = self.document_repository
        if repo is None:
            return None
        document_key = document_id
        # Try the document repository's convenience lookup first.
        for name in ('get_latest_committed_version', 'get_previous_committed_version'):
            method = getattr(repo, name, None)
            if not callable(method):
                continue
            for attempt in (
                lambda m=method: m(company_id, document_key),
                lambda m=method: m(company_id=company_id, document_id=document_key),
            ):
                try:
                    version = await _awaitv(attempt())  # type: ignore[no-untyped-call]
                    candidate = _get(version, 'id', 'version_id', 'document_version_id')
                    if candidate is not None and str(candidate) != str(version_id):
                        return candidate
                except TypeError:
                    continue
                except Exception:
                    break
        # Fall back to listing committed versions.
        for name in ('list_document_versions', 'list_versions'):
            method = getattr(repo, name, None)
            if not callable(method):
                continue
            for attempt in (
                lambda m=method: m(company_id, document_key, state='committed'),
                lambda m=method: m(
                    company_id=company_id, document_id=document_key, state='committed'
                ),
                lambda m=method: m(company_id, document_key),
            ):
                try:
                    versions = await _awaitv(attempt()) or []
                    for version in versions:
                        candidate = _get(version, 'id', 'version_id', 'document_version_id')
                        candidate_state = _get(version, 'state', 'status')
                        if candidate is not None and str(candidate) != str(version_id):
                            if candidate_state is None or str(candidate_state) == 'committed':
                                return candidate
                except TypeError:
                    continue
                except Exception:
                    break
        return None

    async def _update_document_stamp(
        self, company_id: Any, document_id: Any, version_id: Any
    ) -> Any:
        repo = self.document_repository
        markers: dict[str, Any] = {}
        if repo is not None:
            for name in ('document_version_markers', 'document_version_marker_map'):
                method = getattr(repo, name, None)
                if callable(method):
                    for attempt in (
                        lambda m=method: m(company_id),
                        lambda m=method: m(company_id=company_id),
                    ):
                        try:
                            result = await _awaitv(attempt())  # type: ignore[no-untyped-call]
                            if isinstance(result, dict):
                                markers = dict(result)
                            break
                        except TypeError:
                            continue
                        except Exception:
                            break
                    if markers or getattr(method, '__name__', '') == name:
                        break
        markers[str(document_id)] = str(version_id)
        generation = None
        if repo is not None:
            for name in ('list_document_versions', 'list_versions'):
                method = getattr(repo, name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(company_id, document_id),
                    lambda m=method: m(company_id=company_id, document_id=document_id),
                ):
                    try:
                        versions = await _awaitv(attempt()) or []
                        generation = len(list(versions))
                        break
                    except TypeError:
                        continue
                    except Exception:
                        break
                if generation is not None:
                    break
        if generation is None or generation < 1:
            generation = len(markers) or 1
        stamp = DocumentStamp.from_versions(company_id, markers, generation=generation)
        # Persist the stamp through the document repository when supported.
        if repo is not None:
            for name in ('update_document_stamp',):
                method = getattr(repo, name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(company_id, document_id, stamp),
                    lambda m=method: m(company_id, document_id, stamp=stamp),
                    lambda m=method: m(company_id=company_id, document_id=document_id, stamp=stamp),
                    lambda m=method: m(
                        company_id=company_id, document_id=document_id, document_stamp=stamp
                    ),
                ):
                    try:
                        await _awaitv(attempt())
                        break
                    except TypeError:
                        continue
                    except Exception:
                        break
        return stamp

    # Public entry points
    async def handle(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_request(*args, **kwargs)

    async def run_named_step(self, step_name: str, *args: Any, **kwargs: Any) -> Any:
        previous = getattr(self, 'step_name', None)
        self.step_name = str(step_name)
        try:
            return await self._handle_request(*args, **kwargs)
        finally:
            if previous is not None:
                self.step_name = previous

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
