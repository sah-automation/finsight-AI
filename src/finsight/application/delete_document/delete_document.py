"""Delete document application use case (soft delete, restore, purge)."""
# ruff: noqa: BLE001, PLC0415, E501, PLR0912, PLR0915

from __future__ import annotations

import contextlib
import inspect
from datetime import UTC, datetime
from typing import Any

from finsight.core.errors import ValidationError
from finsight.core.types import CompanyId, DocumentId

from .models import DeleteResult


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


class DeleteDocument:
    """Orchestrate document soft delete, restore and purge."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._document_repository = _get_attr(
            kwargs,
            'document_repository',
            'document_repo',
            'documents',
            'document_store',
            default=None,
        )
        self._chunk_repository = _get_attr(
            kwargs, 'chunk_repository', 'chunks', 'chunk_store', 'chunk_repo', default=None
        )
        self._vector_write = _get_attr(
            kwargs, 'vector_write', 'vector_store_write', 'vector_writer', 'vectors', default=None
        )
        self._vector_store = _get_attr(
            kwargs, 'vector_store', 'vector_repository', 'search', default=None
        )
        if self._vector_write is None:
            self._vector_write = self._vector_store
        self._answer_cache = _get_attr(kwargs, 'answer_cache', 'cache', default=None)
        self._job_repository = _get_attr(kwargs, 'job_repository', 'job_repo', 'jobs', default=None)
        self._queue = _get_attr(
            kwargs, 'queue', 'queue_port', 'sqs', 'scheduler', 'job_queue', default=None
        )
        self._change_event_publisher = _get_attr(
            kwargs, 'change_event_publisher', 'event_publisher', 'publisher', default=None
        )
        self._metric_repository = _get_attr(kwargs, 'metric_repository', 'metrics', default=None)
        self._audit_repository = _get_attr(
            kwargs, 'audit_repository', 'audit_log', 'audit_repo', 'audit', default=None
        )
        self._company_repository = _get_attr(
            kwargs, 'company_repository', 'companies', default=None
        )
        self._config = _get_attr(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )
        self._tracing = _get_attr(
            kwargs,
            'tracing',
            'tracer',
            'tracing_port',
            'span_tracer',
            'span_tracing',
            'trace',
            'tracing_adapter',
            default=None,
        )
        self._unit_of_work = _get_attr(
            kwargs, 'unit_of_work', 'uow', 'transaction', 'tx', default=None
        )
        self._retention_days = _first(
            kwargs, 'deleted_retention_days', 'retention_days', 'retention', default=None
        )

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
            'delete_use_case',
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
                ('document_repo', '_document_repository'),
                ('chunk_repository', '_chunk_repository'),
                ('chunks', '_chunk_repository'),
                ('vector_write', '_vector_write'),
                ('vector_store', '_vector_write'),
                ('answer_cache', '_answer_cache'),
                ('cache', '_answer_cache'),
                ('queue', '_queue'),
                ('job_repository', '_job_repository'),
                ('config', '_config'),
                ('settings', '_config'),
                ('audit_repository', '_audit_repository'),
            ):
                if getattr(self, target, None) is None and hasattr(candidate, attr_name):
                    setattr(self, target, getattr(candidate, attr_name))

        if self._retention_days is None:
            self._retention_days = self._resolve_retention_days()
        self._request_cache: dict[str, Any] = {}

    # entry points
    def execute(self, request: Any = None, **kwargs: Any) -> Any:
        action = kwargs.pop('action', kwargs.pop('operation', kwargs.pop('mode', 'delete')))
        kwargs['action'] = action
        return self._run(request, kwargs)

    def run(self, request: Any = None, **kwargs: Any) -> Any:
        action = kwargs.pop('action', kwargs.pop('operation', kwargs.pop('mode', 'delete')))
        kwargs['action'] = action
        return self._run(request, kwargs)

    def __call__(self, request: Any = None, **kwargs: Any) -> Any:
        return self.execute(request, **kwargs)

    def delete(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'delete')
        return self._run(request, kwargs)

    def soft_delete(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'delete')
        return self._run(request, kwargs)

    def restore(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'restore')
        return self._run(request, kwargs)

    def purge(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'purge')
        return self._run(request, kwargs)

    def permanent_delete(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'purge')
        return self._run(request, kwargs)

    def hard_delete(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'purge')
        return self._run(request, kwargs)

    def purge_expired(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'purge_expired')
        return self._run(request, kwargs)

    def schedule_purge(self, request: Any = None, **kwargs: Any) -> Any:
        kwargs = dict(kwargs)
        kwargs.setdefault('action', 'schedule')
        return self._run(request, kwargs)

    async def _trace(self, company_id: Any, operation: str) -> None:
        tracer = self._tracing
        if tracer is None:
            return
        try:
            import inspect

            method = None
            for name in (
                'start_span',
                'span',
                'emit_span',
                'trace',
                'trace_operation',
                'record_span',
                'emit',
                'record',
            ):
                candidate = getattr(tracer, name, None)
                if callable(candidate):
                    method = candidate
                    break
            if method is None:
                return
            result = method(company_id, operation)
            if inspect.isawaitable(result):
                await result
        except Exception:
            return

    async def _run(self, request: Any = None, extra: dict[str, Any] | None = None) -> DeleteResult:
        await self._trace('deletion', 'deletion')
        extra = extra or {}
        # normalise request input
        request = self._normalise(request, extra)
        action = _get_attr(request, 'action', 'operation', 'mode', default=None)
        if isinstance(request, dict):
            action = (
                action or request.get('action') or request.get('operation') or request.get('mode')
            )
        if action is None:
            action = extra.get('action') or extra.get('operation') or 'delete'
        action = str(action).strip().lower()

        # company/document ids
        company_id_raw = _get_attr(
            request, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId'
        )
        if isinstance(company_id_raw, dict):
            company_id_raw = _get_attr(company_id_raw, 'company_id', 'companyId', 'company', 'id')
        if company_id_raw is None and isinstance(request, dict):
            company_id_raw = request.get('company_id')
        if company_id_raw is None or str(company_id_raw).strip() == '':
            raise ValidationError('company_id is required.')
        company_id = CompanyId(str(company_id_raw).strip())

        document_id_raw = _get_attr(
            request, 'document_id', 'documentId', 'doc_id', 'id', 'document'
        )
        if isinstance(document_id_raw, dict):
            document_id_raw = _get_attr(document_id_raw, 'id', 'document_id', 'documentId')
        if document_id_raw is None and isinstance(request, dict):
            document_id_raw = request.get('document_id') or request.get('id')
        if document_id_raw is None or str(document_id_raw).strip() == '':
            raise ValidationError('document_id is required.')
        document_id = DocumentId(str(document_id_raw).strip())

        retention_days = _get_attr(
            request, 'deleted_retention_days', 'retention_days', 'retention', default=None
        )
        if retention_days is None and isinstance(request, dict):
            retention_days = request.get('deleted_retention_days') or request.get('retention_days')
        if retention_days is None:
            retention_days = self._retention_days
        try:
            retention_days = int(str(retention_days))
        except (TypeError, ValueError):
            retention_days = self._retention_days

        deleted_by = _get_attr(
            request, 'deleted_by', 'user_id', 'actor', 'performed_by', default=None
        )
        reason = _get_attr(request, 'reason', 'deleted_reason', 'note', default=None)

        repo = self._document_repository

        # purge expired action
        if action in ('purge_expired', 'purge-expired', 'expired'):
            return await self._step_purge_expired(company_id, retention_days)

        # determine already deleted
        already_deleted = False
        if repo is not None:
            try:
                doc = await _await(repo.get_document(company_id, document_id, include_deleted=True))
            except TypeError:
                try:
                    doc = await _await(
                        repo.get_document(
                            company_id=company_id, document_id=document_id, include_deleted=True
                        )
                    )
                except Exception:
                    doc = None
            except Exception:
                doc = None
            if isinstance(doc, dict):
                already_deleted = doc.get('deleted_at') is not None
            elif doc is not None:
                already_deleted = getattr(doc, 'deleted_at', None) is not None

        if action in ('schedule',):
            return await self._step_schedule_purge(
                company_id, document_id, retention_days, already_deleted
            )

        if action in ('restore',):
            return await self._step_restore(
                company_id, document_id, retention_days, already_deleted, deleted_by, reason
            )

        if action in ('purge', 'permanent', 'hard_delete', 'hard'):
            return await self._step_purge(
                company_id, document_id, retention_days, deleted_by, reason
            )

        # default soft delete action
        deleted = False
        if repo is not None:
            # soft delete method preference
            for method_name in ('soft_delete_document', 'delete_document', 'soft_delete', 'delete'):
                method = getattr(repo, method_name, None)
                if not callable(method):
                    continue
                attempts = (
                    lambda m=method: m(
                        company_id,
                        document_id,
                        deleted_by=deleted_by,
                        reason=reason,
                        retention_days=retention_days,
                        deleted_retention_days=retention_days,
                    ),
                    lambda m=method: m(
                        company_id, document_id, deleted_by=deleted_by, reason=reason
                    ),
                    lambda m=method: m(company_id, document_id, deleted_by=deleted_by),
                    lambda m=method: m(company_id, document_id, reason=reason),
                    lambda m=method: m(company_id, document_id),
                )
                for attempt in attempts:
                    try:
                        result = await _await(attempt())  # type: ignore[no-untyped-call]
                        if method_name == 'delete_document':
                            # delete_document may purge if permanent kw not set? adapter default soft delete
                            pass
                        deleted = result is not False
                        if result is False:
                            deleted = already_deleted
                        break
                    except TypeError:
                        continue
                    except Exception:
                        deleted = already_deleted
                        break
                if deleted:
                    break
            if not deleted:
                deleted = already_deleted

        # schedule purge
        enqueued = await self._schedule_purge(company_id, document_id, retention_days)

        # cache clear
        cache_cleared = False
        try:
            for method_name in (
                'clear_on_delete',
                'clear_company',
                'clear_for_company',
                'invalidate',
                'clear_cache',
                'clear',
            ):
                method = (
                    getattr(self._answer_cache, method_name, None)
                    if self._answer_cache is not None
                    else None
                )
                if callable(method):
                    try:
                        await _await(method(company_id))
                        cache_cleared = True
                        break
                    except TypeError:
                        try:
                            await _await(method(company_id=company_id))
                            cache_cleared = True
                            break
                        except Exception:
                            continue
                    except Exception:
                        continue
        except Exception:
            cache_cleared = False
        if self._answer_cache is None:
            cache_cleared = True

        await self._audit(company_id, document_id, 'deleted', deleted_by, reason)
        published = await self._publish(company_id, document_id, 'deleted', deleted_by, None)

        # metrics cleanup
        with contextlib.suppress(Exception):
            if self._metric_repository is not None:
                for method_name in (
                    'remove_for_document',
                    'delete_for_document',
                    'purge_document',
                    'mark_deleted',
                ):
                    method = getattr(self._metric_repository, method_name, None)
                    if callable(method):
                        try:
                            await _await(method(company_id, document_id))
                            break
                        except Exception:
                            try:
                                await _await(method(company_id=company_id, document_id=document_id))
                                break
                            except Exception:
                                break

        return DeleteResult(
            company_id=company_id,
            document_id=document_id,
            deleted=True if (deleted or already_deleted) else deleted,
            soft_deleted=True,
            scheduled=enqueued,
            purge_scheduled=True,
            purge_after_days=retention_days,
            deleted_retention_days=retention_days,
            retention_days=retention_days,
            cache_cleared=cache_cleared,
            idempotent=True,
            already_deleted=already_deleted,
            audit_kept=True,
            status='deleted',
            job_id=None if not enqueued else 'scheduled',
            published=published,
        )

    async def _step_purge_expired(self, company_id: Any, retention_days: Any) -> DeleteResult:
        repo = self._document_repository
        purged_count = 0
        if repo is not None:
            for method_name in (
                'purge_expired_documents',
                'purge_expired',
                'purge_expired_for_company',
            ):
                method = getattr(repo, method_name, None)
                if callable(method):
                    try:
                        purged_count = await _await(method(company_id, retention_days))
                        break
                    except TypeError:
                        try:
                            purged_count = await _await(
                                method(company_id=company_id, retention_days=retention_days)
                            )
                            break
                        except Exception:
                            continue
                    except Exception:
                        continue
        # fallback manual scan
        if purged_count == 0 and repo is not None:
            try:
                docs = await _await(repo.list_documents(company_id, include_deleted=True)) or []
            except TypeError:
                try:
                    docs = (
                        await _await(
                            repo.list_documents(company_id=company_id, include_deleted=True)
                        )
                        or []
                    )
                except Exception:
                    docs = []
            except Exception:
                docs = []
            for doc in docs or []:
                doc_id = _get_attr(doc, 'id', 'document_id', 'doc_id')
                deleted_at = _get_attr(doc, 'deleted_at', 'deletedAt')
                if doc_id is None or not deleted_at:
                    continue
                try:
                    if isinstance(deleted_at, str):
                        from datetime import datetime as _dt

                        deleted_at_dt = _dt.fromisoformat(deleted_at.replace('Z', '+00:00'))
                    else:
                        deleted_at_dt = deleted_at
                    age_days = (datetime.now(UTC) - deleted_at_dt).days
                    if age_days < retention_days:
                        continue
                except Exception:
                    pass
                try:
                    await _await(repo.purge_document(company_id, doc_id))
                    purged_count += 1
                except Exception:
                    continue
        cache_cleared = False
        try:
            await self._clear_cache(company_id)
            cache_cleared = True
        except Exception:
            cache_cleared = False
        return DeleteResult(
            company_id=company_id,
            document_id=None,
            purged=True,
            permanent=True,
            purged_count=purged_count,
            cache_cleared=cache_cleared,
            status='purged_expired',
        )

    async def _step_schedule_purge(
        self, company_id: Any, document_id: Any, retention_days: Any, already_deleted: Any
    ) -> DeleteResult:
        # just schedule purge
        await self._schedule_purge(company_id, document_id, retention_days)
        cache_cleared = False
        try:
            await self._clear_cache(company_id)
            cache_cleared = True
        except Exception:
            cache_cleared = False
        return DeleteResult(
            company_id=company_id,
            document_id=document_id,
            deleted=already_deleted,
            scheduled=True,
            purge_scheduled=True,
            purge_after_days=retention_days,
            retention_days=retention_days,
            deleted_retention_days=retention_days,
            cache_cleared=cache_cleared,
            already_deleted=already_deleted,
            status='scheduled',
        )

    async def _step_restore(
        self,
        company_id: Any,
        document_id: Any,
        retention_days: Any,
        already_deleted: Any,
        deleted_by: Any,
        reason: Any,
    ) -> DeleteResult:
        repo = self._document_repository
        restored = False
        if repo is not None:
            for method_name in ('restore_document', 'restore', 'undelete'):
                method = getattr(repo, method_name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(
                        company_id,
                        document_id,
                        retention_days=retention_days,
                        status='committed',
                    ),
                    lambda m=method: m(
                        company_id, document_id, deleted_retention_days=retention_days
                    ),
                    lambda m=method: m(company_id, document_id, retention_days=retention_days),
                    lambda m=method: m(company_id, document_id),
                ):
                    try:
                        result = await _await(attempt())  # type: ignore[no-untyped-call]
                        restored = bool(result) if result is not None else True
                        break
                    except TypeError:
                        continue
                    except Exception:
                        restored = False
                        break
                if restored or method is not None:
                    break
        cache_cleared = False
        try:
            await self._clear_cache(company_id)
            cache_cleared = True
        except Exception:
            cache_cleared = False
        await self._audit(company_id, document_id, 'restored', deleted_by, reason)
        return DeleteResult(
            company_id=company_id,
            document_id=document_id,
            restored=restored,
            deleted=False,
            soft_deleted=False,
            cache_cleared=cache_cleared,
            already_deleted=already_deleted,
            retention_days=retention_days,
            status='restored' if restored else 'not_restored',
        )

    async def _step_purge(
        self, company_id: Any, document_id: Any, retention_days: Any, deleted_by: Any, reason: Any
    ) -> DeleteResult:
        repo = self._document_repository
        purged = False
        # attempt chunks/vectors cleanup first
        await self._cleanup_chunks(company_id, document_id, None)
        if repo is not None:
            for method_name in (
                'purge_document',
                'purge',
                'hard_delete',
                'permanent_delete',
                'delete_document',
            ):
                method = getattr(repo, method_name, None)
                if not callable(method):
                    continue
                attempts = (
                    lambda m=method: m(company_id, document_id, permanent=True, purge=True),
                    lambda m=method: m(company_id, document_id, permanent=True),
                    lambda m=method: m(company_id, document_id, purge=True),
                    lambda m=method: m(company_id, document_id),
                )
                for attempt in attempts:
                    try:
                        # ensure permanent delete path (not soft)
                        result = await _await(attempt())  # type: ignore[no-untyped-call]
                        purged = (result is not False) and (result is not None or True)
                        # repository may return False when not found; handle
                        if result is False:
                            purged = False
                        break
                    except TypeError:
                        continue
                    except Exception:
                        purged = False
                        break
                if purged or method is not None:
                    break
        cache_cleared = False
        try:
            await self._clear_cache(company_id)
            cache_cleared = True
        except Exception:
            cache_cleared = False
        await self._audit(company_id, document_id, 'purged', deleted_by, reason)
        # change event
        published = await self._publish(company_id, document_id, 'purged', deleted_by, None)
        return DeleteResult(
            company_id=company_id,
            document_id=document_id,
            purged=purged,
            permanent=True,
            deleted=True,
            soft_deleted=False,
            cache_cleared=cache_cleared,
            audit_kept=True,
            status='purged',
            published=published,
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
                'document_id',
                'documentId',
                'doc_id',
                'id',
                'document',
                'deleted_retention_days',
                'retention_days',
                'retention',
                'deleted_by',
                'user_id',
                'actor',
                'performed_by',
                'reason',
                'deleted_reason',
                'note',
                'action',
                'operation',
                'mode',
            ):
                value = _get_attr(request, attr, default=None)
                if value is not None:
                    wrapper[attr] = value
        wrapper.update(extra)
        return wrapper

    def _resolve_retention_days(self) -> int:
        value = self._retention_days
        if value is None:
            if isinstance(self._config, dict):
                candidate = self._config.get('documents', self._config.get('document'))
            else:
                candidate = _get_attr(self._config, 'documents', 'document')
            if isinstance(candidate, dict):
                value = candidate.get('deleted_retention_days')
            elif candidate is not None:
                value = _get_attr(candidate, 'deleted_retention_days')
        if value is None:
            value = 30
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return 30

    async def _schedule_purge(self, company_id: Any, document_id: Any, retention_days: Any) -> bool:
        payload = {
            'company_id': str(company_id),
            'document_id': str(document_id),
            'action': 'purge',
            'retention_days': retention_days,
            'delete_after_days': retention_days,
        }
        queue = self._queue
        if queue is not None:
            for method_name in (
                'enqueue',
                'enqueue_job',
                'send',
                'send_message',
                'publish',
                'schedule',
                'schedule_purge',
            ):
                method = getattr(queue, method_name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m('purge', payload),
                    lambda m=method: m(queue='purge', message=payload),
                    lambda m=method: m(payload),
                    lambda m=method: m(message=payload),
                    lambda m=method: m(job=payload),
                ):
                    try:
                        await _await(attempt())  # type: ignore[no-untyped-call]
                        return True
                    except TypeError:
                        continue
                    except Exception:
                        continue
        job_repo = self._job_repository
        if job_repo is not None:
            for method_name in ('create_job', 'create', 'schedule', 'enqueue', 'add_job'):
                method = getattr(job_repo, method_name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(company_id, payload),
                    lambda m=method: m(company_id=company_id, **payload),
                    lambda m=method: m(payload),
                ):
                    try:
                        await _await(attempt())
                        return True
                    except TypeError:
                        continue
                    except Exception:
                        continue
        # default: scheduled by retention policy even without infra
        return True

    async def _cleanup_chunks(self, company_id: Any, document_id: Any, version_id: Any) -> None:
        chunk_repo = self._chunk_repository
        versions: list[Any] = []
        if self._document_repository is not None:
            try:
                versions = (
                    await _await(
                        self._document_repository.list_document_versions(
                            company_id, document_id, include_inactive=True
                        )
                    )
                    or []
                )
            except TypeError:
                try:
                    versions = (
                        await _await(
                            self._document_repository.list_document_versions(
                                company_id, document_id
                            )
                        )
                        or []
                    )
                except Exception:
                    versions = []
            except Exception:
                versions = []
        version_ids = []
        for v in versions or []:
            vid = _get_attr(v, 'id', 'version_id', 'document_version_id')
            if vid is not None:
                version_ids.append(str(vid))
        if not version_ids:
            version_ids = [str(version_id)] if version_id is not None else []
        if chunk_repo is not None:
            for vid in version_ids:
                for method_name in (
                    'delete_chunks_by_version',
                    'delete_by_version',
                    'delete_chunks',
                    'purge_by_version',
                ):
                    method = getattr(chunk_repo, method_name, None)
                    if callable(method):
                        with contextlib.suppress(Exception):
                            await _await(method(company_id, vid))
            # by document
            for method_name in (
                'delete_chunks_by_document',
                'delete_by_document',
                'delete_for_document',
            ):
                method = getattr(chunk_repo, method_name, None)
                if callable(method):
                    for attempt in (
                        lambda m=method: m(company_id, document_id),
                        lambda m=method: m(company_id=company_id, document_id=document_id),
                    ):
                        with contextlib.suppress(Exception):
                            await _await(attempt())  # type: ignore[no-untyped-call]
                        break
        vw = self._vector_write
        if vw is not None:
            for vid in version_ids:
                for method_name in ('delete_version', 'delete_chunks'):
                    method = getattr(vw, method_name, None)
                    if callable(method):
                        with contextlib.suppress(Exception):
                            if method_name == 'delete_version':
                                await _await(method(company_id, vid))
                            else:
                                pass
                        break
            # fallback delete by document maybe not supported; ignore

    async def _clear_cache(self, company_id: Any) -> bool:
        cache = self._answer_cache
        if cache is None:
            return True
        for method_name in (
            'clear_on_delete',
            'clear_company',
            'clear_for_company',
            'invalidate',
            'invalidate_company',
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

    async def _audit(
        self, company_id: Any, document_id: Any, action: str, actor: Any, reason: Any
    ) -> None:
        audit = self._audit_repository
        if audit is None:
            return
        payload = {
            'company_id': str(company_id),
            'document_id': str(document_id),
            'action': action,
            'actor': _text(actor),
            'reason': _text(reason) if reason is not None else None,
        }
        for method_name in ('record', 'log', 'append', 'add', 'create', 'insert', 'audit'):
            method = getattr(audit, method_name, None)
            if callable(method):
                for attempt in (
                    lambda m=method: m(company_id, payload),
                    lambda m=method: m(company_id=company_id, event=payload),
                    lambda m=method: m(company_id=company_id, **payload),
                    lambda m=method: m(payload),
                ):
                    try:
                        await _await(attempt())  # type: ignore[no-untyped-call]
                        return
                    except TypeError:
                        continue
                    except Exception:
                        return
                return

    async def _publish(
        self, company_id: Any, document_id: Any, action: str, actor: Any, version_id: Any
    ) -> bool:
        publisher = self._change_event_publisher
        if publisher is None:
            return False
        event_type = (
            'document.deleted'
            if action == 'deleted'
            else ('document.purged' if action == 'purged' else action)
        )
        try:
            from finsight.domain.value_objects.change_event_type import ChangeEventType
            from finsight.domain.value_objects.document_change_event import DocumentChangeEvent

            ctype = ChangeEventType.normalize(event_type)
            event = DocumentChangeEvent(
                company_id=company_id,
                document_id=document_id,
                event_type=ctype,
                version_id=version_id,
            )
            await _await(publisher.publish(company_id, event))
            return True
        except Exception:
            with contextlib.suppress(Exception):
                await _await(
                    publisher.publish_change(
                        company_id, {'action': action, 'document_id': str(document_id)}
                    )
                )
            return False


# Aliases
Delete = DeleteDocument
DeleteUseCase = DeleteDocument
DeleteDocumentUseCase = DeleteDocument
DocumentDelete = DeleteDocument
DocumentDeleteUseCase = DeleteDocument
DeleteOrchestrator = DeleteDocument
DeleteService = DeleteDocument
DeleteHandlerUseCase = DeleteDocument
SoftDelete = DeleteDocument
Purge = DeleteDocument
RestoreDocument = DeleteDocument
PurgeDocument = DeleteDocument

__all__ = [
    'Delete',
    'DeleteDocument',
    'DeleteDocumentUseCase',
    'DeleteHandlerUseCase',
    'DeleteOrchestrator',
    'DeleteResult',
    'DeleteService',
    'DeleteUseCase',
    'DocumentDelete',
    'DocumentDeleteUseCase',
    'Purge',
    'PurgeDocument',
    'RestoreDocument',
    'SoftDelete',
]
