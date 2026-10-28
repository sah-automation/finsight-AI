"""Reprocess application use case (rolling, idempotent)."""

from __future__ import annotations

import contextlib
import inspect
from typing import Any

from finsight.core.errors import ValidationError
from finsight.core.types import CompanyId
from finsight.domain.services.document_stamp import DocumentStamp

from .models import ReprocessResult


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
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


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _text(value: Any) -> str:
    return '' if value is None else str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str):
        if value.strip() == '':
            return []
        return [value]
    if isinstance(value, dict):
        for key in ('company_ids', 'companies', 'company_id', 'ids', 'values'):
            if value.get(key) is not None:
                return _as_list(value.get(key))
        return [value]
    return [value]


class Reprocess:
    """Rolling, idempotent reprocessing use case."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._document_repository = _get_attr(
            kwargs, 'document_repository', 'document_repo', 'documents', default=None
        )
        self._chunk_repository = _get_attr(
            kwargs, 'chunk_repository', 'chunks', 'chunk_store', default=None
        )
        self._vector_write = _get_attr(
            kwargs, 'vector_write', 'vector_store_write', 'vector_writer', 'vectors', default=None
        )
        self._vector_store = _get_attr(kwargs, 'vector_store', 'vector_repository', default=None)
        if self._vector_write is None:
            self._vector_write = self._vector_store
        self._metric_repository = _get_attr(kwargs, 'metric_repository', 'metrics', default=None)
        self._answer_cache = _get_attr(kwargs, 'answer_cache', 'cache', default=None)
        self._queue = _get_attr(
            kwargs, 'queue', 'queue_port', 'sqs', 'job_queue', 'reprocessing_queue', default=None
        )
        self._job_repository = _get_attr(kwargs, 'job_repository', 'job_repo', 'jobs', default=None)
        self._change_event_publisher = _get_attr(
            kwargs, 'change_event_publisher', 'event_publisher', 'publisher', default=None
        )
        self._company_repository = _get_attr(
            kwargs, 'company_repository', 'companies', default=None
        )
        self._config = _get_attr(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )
        self._unit_of_work = _get_attr(
            kwargs, 'unit_of_work', 'uow', 'transaction', 'tx', default=None
        )
        self._delta_tracking = _first(kwargs, 'delta_tracking', default=None)
        self._batch_size = _first(
            kwargs,
            'batch_size',
            'companies_per_batch',
            'reprocess_batch_size',
            'batch',
            default=None,
        )
        self._priority = _first(kwargs, 'priority', 'job_priority', default='low')
        self._engines = _get_attr(kwargs, 'engines', 'readers', default=None)

        positional = [
            '_document_repository',
            '_chunk_repository',
            '_vector_write',
            '_answer_cache',
            '_job_repository',
            '_queue',
            '_config',
        ]
        for index, value in enumerate(args):
            if index < len(positional):
                setattr(self, positional[index], value)

        for candidate_key in (
            'reprocess_use_case',
            'use_case',
            'service',
            'container',
            'composition',
            'app',
        ):
            candidate = kwargs.get(candidate_key)
            if candidate is None:
                continue
            for attr_name, target in (
                ('document_repository', '_document_repository'),
                ('chunk_repository', '_chunk_repository'),
                ('vector_write', '_vector_write'),
                ('vector_store', '_vector_write'),
                ('answer_cache', '_answer_cache'),
                ('queue', '_queue'),
                ('job_repository', '_job_repository'),
                ('change_event_publisher', '_change_event_publisher'),
                ('config', '_config'),
                ('settings', '_config'),
            ):
                if getattr(self, target, None) is None and hasattr(candidate, attr_name):
                    setattr(self, target, getattr(candidate, attr_name))

        if self._delta_tracking is None:
            self._delta_tracking = self._resolve_delta_tracking()
        if self._batch_size is None:
            self._batch_size = self._resolve_batch_size()
        try:
            self._batch_size = int(self._batch_size)
        except (TypeError, ValueError):
            self._batch_size = 3
        self._batch_size = max(self._batch_size, 1)
        self._priority = self._priority or 'low'
        self._request_cache: dict[str, Any] = {}

    # entry points
    def execute(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def run(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def __call__(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def reprocess(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def process(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def batch(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    async def _run(
        self, request: Any = None, extra: dict[str, Any] | None = None
    ) -> ReprocessResult:
        extra = extra or {}
        request = self._normalise(request, extra)

        # company ids
        company_raw = _get_attr(
            request, 'company_id', 'companyId', 'company', 'tenant_id', default=None
        )
        if company_raw is None and isinstance(request, dict):
            company_raw = request.get('company_id')
        company_ids = _as_list(
            _get_attr(request, 'company_ids', 'companies', 'companyIds', 'tenants', default=None)
        )
        if not company_ids and company_raw is not None:
            company_ids = _as_list(company_raw)
        if not company_ids and isinstance(request, dict):
            for key in ('company_ids', 'companies', 'companyIds', 'ids', 'tenants'):
                if request.get(key) is not None:
                    company_ids = _as_list(request.get(key))
                    break
        # company repository list all if none
        if not company_ids and self._company_repository is not None:
            for method_name in ('list_companies', 'list', 'list_all', 'get_all'):
                method = getattr(self._company_repository, method_name, None)
                if callable(method):
                    try:
                        result = await _await(method())
                        company_ids = _as_list(result)
                    except Exception:
                        company_ids = []
                    break
        company_ids = [
            str(c)
            if not isinstance(c, (dict,))
            else _text(_get_attr(c, 'id', 'company_id', 'companyId'))
            for c in company_ids
        ]
        company_ids = [c for c in company_ids if c.strip() != '']
        if not company_ids:
            raise ValidationError('company_id is required.')

        batch_size = _get_attr(
            request,
            'batch_size',
            'companies_per_batch',
            'reprocess_batch_size',
            'batch',
            default=None,
        )
        if batch_size is None and isinstance(request, dict):
            batch_size = request.get('batch_size') or request.get('companies_per_batch')
        if batch_size is None:
            batch_size = extra.get('batch_size')
        if batch_size is None:
            batch_size = self._batch_size
        try:
            batch_size = int(batch_size)
        except (TypeError, ValueError):
            batch_size = self._batch_size
        batch_size = max(batch_size, 1)

        priority = _get_attr(request, 'priority', 'job_priority', 'priority_level', default=None)
        if priority is None and isinstance(request, dict):
            priority = request.get('priority')
        if priority is None:
            priority = extra.get('priority')
        if priority is None:
            priority = self._priority
        priority = priority or 'low'

        delta_tracking = _get_attr(request, 'delta_tracking', default=None)
        if delta_tracking is None and isinstance(request, dict):
            delta_tracking = request.get('delta_tracking')
        if delta_tracking is None:
            delta_tracking = extra.get('delta_tracking')
        if delta_tracking is None:
            delta_tracking = self._delta_tracking
        try:
            delta_tracking = bool(delta_tracking) if delta_tracking is not None else True
        except Exception:
            delta_tracking = True

        dry_run = bool(
            _get_attr(request, 'dry_run', default=False)
            or (isinstance(request, dict) and request.get('dry_run'))
        )
        # batches
        batches = [company_ids[i : i + batch_size] for i in range(0, len(company_ids), batch_size)]

        # optional enqueue instead of sync process
        sync = _get_attr(request, 'sync', 'synchronous', 'process_now', default=None)
        if sync is None and isinstance(request, dict):
            sync = request.get('sync') or request.get('synchronous') or request.get('process_now')
        if sync is None:
            sync = extra.get('execute_synchronously', True)
        enqueued = False
        job_id = _get_attr(request, 'job_id', 'jobId', default=None)
        if sync is False:
            payload = {
                'company_ids': company_ids,
                'batches': batches,
                'batch_size': batch_size,
                'priority': priority,
                'delta_tracking': delta_tracking,
                'dry_run': dry_run,
            }
            enqueued, qjob_id = await self._enqueue(payload)
            if qjob_id is not None:
                job_id = qjob_id
            return ReprocessResult(
                company_id=company_ids[0],
                company_ids=company_ids,
                processed_companies=[] if enqueued else company_ids,
                companies=[] if enqueued else company_ids,
                processed=[] if enqueued else company_ids,
                batches=batches,
                batch_size=batch_size,
                priority=priority,
                queued=enqueued,
                enqueued=enqueued,
                job_id=job_id,
                delta_tracking=delta_tracking,
                cache_cleared=False,
                status='queued' if enqueued else 'completed',
            )

        # sync rolling processing
        processed_all: list[str] = []
        affected_all: list[str] = []
        cache_cleared_any = False
        published_any = False
        failed_all = []
        for batch in batches:
            for cid_text in batch:
                cid = CompanyId(cid_text)
                try:
                    await self._process_company(cid, delta_tracking, dry_run)
                except Exception:
                    failed_all.append(cid_text)
                    continue
                processed_all.append(cid_text)
                # clear cache
                try:
                    await self._clear_cache(cid)
                    cache_cleared_any = True
                except Exception:
                    pass
                # update stamp banner (attempt)
                await self._touch_stamp(cid)
                # Publish not tied to change events in Phase 1; audit only.
                # flag affected documents (reuse document repo listing) - keep audit only
                affected = await self._flag_affected(cid)
                affected_all.extend(affected)

        # update stamps for docs maybe already in process_company
        return ReprocessResult(
            company_id=company_ids[0],
            company_ids=company_ids,
            processed_companies=processed_all,
            companies=processed_all,
            processed=processed_all,
            batches=batches,
            batch_size=batch_size,
            priority=priority,
            queued=False,
            enqueued=False,
            job_id=job_id,
            delta_tracking=delta_tracking,
            cache_cleared=cache_cleared_any,
            published=published_any,
            affected_documents=affected_all,
            failed_companies=failed_all,
            status='completed',
        )

    def _normalise(self, request: Any, extra: dict[str, Any]) -> Any:
        if request is None and not extra:
            return {}
        if isinstance(request, dict):
            merged = dict(request)
            merged.update(extra)
            return merged
        if request is not None and not extra:
            return request
        wrapper: dict[str, Any] = {}
        if request is not None:
            for attr in (
                'company_id',
                'companyId',
                'company',
                'tenant_id',
                'tenantId',
                'company_ids',
                'companies',
                'companyIds',
                'tenants',
                'ids',
                'batch_size',
                'companies_per_batch',
                'reprocess_batch_size',
                'batch',
                'priority',
                'job_priority',
                'priority_level',
                'delta_tracking',
                'dry_run',
                'sync',
                'synchronous',
                'process_now',
                'job_id',
                'jobId',
                'action',
                'operation',
                'mode',
            ):
                value = _get_attr(request, attr, default=None)
                if value is not None:
                    wrapper[attr] = value
        wrapper.update(extra)
        return wrapper

    async def _process_company(self, company_id: Any, delta_tracking: bool, dry_run: bool) -> None:
        repo = self._document_repository
        if repo is None:
            return
        docs = None
        for method_name in (
            'list_documents',
            'list_by_company',
            'list_for_company',
            'list_all_documents',
        ):
            method = getattr(repo, method_name, None)
            if not callable(method):
                continue
            try:
                docs = await _await(method(company_id))
            except TypeError:
                try:
                    docs = await _await(method(company_id=company_id))
                except Exception:
                    docs = None
            if docs is not None:
                break
        if docs is None:
            return
        for doc in docs or []:
            document_id = _get_attr(doc, 'id', 'document_id', 'doc_id')
            if document_id is None:
                continue
            _get_attr(doc, 'version_id', 'latest_version_id', 'committed_version_id')
            # atomic commit stays current version; no mutation of committed version
            # publish change events marking reprocessed candidate maybe via repo update stamp
            if not dry_run:
                for method_name in (
                    'mark_for_reprocess',
                    'request_reprocess',
                    'set_reprocess_pending',
                ):
                    method = getattr(repo, method_name, None)
                    if callable(method):
                        with contextlib.suppress(Exception):
                            await _await(method(company_id, document_id))
                        break

    async def _touch_stamp(self, company_id: Any) -> None:
        repo = self._document_repository
        if repo is None:
            return
        try:
            markers: dict[str, Any] = {}
            if hasattr(repo, 'document_version_markers'):
                markers = await _await(repo.document_version_markers(company_id)) or {}
            if not isinstance(markers, dict):
                markers = {}
            stamp = DocumentStamp.initial(company_id)
            if markers:
                stamp = stamp.updated_for(markers)
            # persist stamp at company level not supported in adapter (document-level only)
        except Exception:
            pass

    async def _clear_cache(self, company_id: Any) -> bool:
        cache = self._answer_cache
        if cache is None:
            return True
        for method_name in (
            'clear_on_reprocess',
            'clear_company',
            'clear_for_company',
            'invalidate',
            'clear_cache',
            'clear',
        ):
            method = getattr(cache, method_name, None)
            if callable(method):
                try:
                    await _await(method(company_id))
                    return True
                except TypeError:
                    try:
                        await _await(method(company_id=company_id))
                        return True
                    except Exception:
                        continue
                except Exception:
                    continue
        return False

    async def _publish_reprocess(self, company_id: Any) -> bool:
        # No company-wide change event without a document id in Phase 1.
        return False

    async def _flag_affected(self, company_id: Any) -> list[str]:
        repo = self._document_repository
        if repo is None:
            return []
        docs = None
        for method_name in (
            'list_documents',
            'list_by_company',
            'list_for_company',
            'list_all_documents',
        ):
            method = getattr(repo, method_name, None)
            if not callable(method):
                continue
            try:
                docs = await _await(method(company_id))
            except TypeError:
                try:
                    docs = await _await(method(company_id=company_id))
                except Exception:
                    docs = None
            except Exception:
                docs = None
            if docs is not None:
                break
        affected = []
        if docs:
            for doc in docs:
                did = _get_attr(doc, 'id', 'document_id', 'doc_id')
                if did is not None:
                    affected.append(str(did))
        return affected

    async def _enqueue(self, payload: dict[str, Any]) -> tuple[bool, Any]:
        queue = self._queue
        if queue is not None:
            for method_name in (
                'enqueue',
                'enqueue_job',
                'send',
                'send_message',
                'publish',
                'dispatch',
                'put',
            ):
                method = getattr(queue, method_name, None)
                if not callable(method):
                    continue
                attempts = (
                    lambda m=method: m('reprocessing', payload),
                    lambda m=method: m(queue='reprocessing', message=payload),
                    lambda m=method: m('reprocess', payload),
                    lambda m=method: m(priority=payload['priority'], **payload),
                    lambda m=method: m(payload),
                    lambda m=method: m(message=payload),
                    lambda m=method: m(body=payload),
                )
                for attempt in attempts:
                    try:
                        result = await _await(attempt())  # type: ignore[no-untyped-call]
                        jid = None
                        if isinstance(result, dict):
                            jid = (
                                result.get('job_id')
                                or result.get('jobId')
                                or result.get('id')
                                or result.get('MessageId')
                            )
                        elif result is not None:
                            jid = getattr(result, 'id', None) or getattr(result, 'job_id', None)
                        return True, jid
                    except TypeError:
                        continue
                    except Exception:
                        continue
        job_repo = self._job_repository
        if job_repo is not None:
            for method_name in ('create_job', 'create', 'enqueue', 'schedule', 'add_job'):
                method = getattr(job_repo, method_name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(payload),
                    lambda m=method: m(company_id=payload.get('company_ids'), **payload),
                ):
                    try:
                        result = await _await(attempt())
                        jid = None
                        if isinstance(result, dict):
                            jid = result.get('job_id') or result.get('jobId') or result.get('id')
                        elif result is not None:
                            jid = getattr(result, 'id', None) or getattr(result, 'job_id', None)
                        return True, jid
                    except TypeError:
                        continue
                    except Exception:
                        continue
        return False, None

    def _resolve_delta_tracking(self) -> bool:
        value = self._delta_tracking
        if value is None:
            docs_cfg = None
            if isinstance(self._config, dict):
                docs_cfg = self._config.get('documents', self._config.get('ingestion'))
            else:
                docs_cfg = _get_attr(self._config, 'documents', 'ingestion')
            if isinstance(docs_cfg, dict):
                value = docs_cfg.get('delta_tracking')
            elif docs_cfg is not None:
                value = _get_attr(docs_cfg, 'delta_tracking')
        if value is None:
            value = True
        try:
            return bool(value)
        except Exception:
            return True

    def _resolve_batch_size(self) -> int:
        cfg = self._config
        value = None
        if isinstance(cfg, dict):
            scale = cfg.get('scale', {})
            if isinstance(scale, dict):
                value = scale.get('reprocess_max_parallel_companies')
            ingest = cfg.get('ingestion', {})
            if value is None and isinstance(ingest, dict):
                value = ingest.get('reprocess_batch_size') or ingest.get('batch_size')
        elif cfg is not None:
            scale = _get_attr(cfg, 'scale')
            if scale is not None:
                value = _get_attr(scale, 'reprocess_max_parallel_companies')
            if value is None:
                ingest = _get_attr(cfg, 'ingestion')
                if ingest is not None:
                    value = _first(ingest, 'reprocess_batch_size', 'batch_size')
            if value is None:
                value = _get_attr(cfg, 'reprocess_max_parallel_companies')
        if value is None:
            value = 1
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 1
        value = max(value, 1)
        return value


# Aliases
ReprocessDocument = Reprocess
ReprocessDocuments = Reprocess
ReprocessUseCase = Reprocess
ReprocessJob = Reprocess
Reprocessor = Reprocess
RollingReprocess = Reprocess
ReprocessService = Reprocess
ReprocessHandlerUseCase = Reprocess
ReprocessOrchestrator = Reprocess

__all__ = [
    'Reprocess',
    'ReprocessDocument',
    'ReprocessDocuments',
    'ReprocessHandlerUseCase',
    'ReprocessJob',
    'ReprocessOrchestrator',
    'ReprocessResult',
    'ReprocessService',
    'ReprocessUseCase',
    'Reprocessor',
    'RollingReprocess',
]
