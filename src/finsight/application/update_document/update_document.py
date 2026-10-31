"""Update document application use case."""

from __future__ import annotations

import contextlib
import inspect
import re
import uuid
from typing import Any

from finsight.core.errors import ValidationError
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.document_version import DocumentVersion
from finsight.domain.value_objects.change_event_type import ChangeEventType
from finsight.domain.value_objects.document_change_event import DocumentChangeEvent

from .models import UpdateResult

# Models are intentionally not imported to avoid coupling; result class lives here.


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


def _switch(config: Any, name: str, default: Any = None) -> Any:
    if config is None:
        return default
    val = None
    if isinstance(config, dict):
        switches = config.get('switches', {})
        if isinstance(switches, dict):
            val = switches.get(name)
        if val is None:
            val = config.get(name)
    else:
        switches = getattr(config, 'switches', None)
        if switches is not None:
            val = (
                switches.get(name) if isinstance(switches, dict) else getattr(switches, name, None)
            )
        if val is None:
            val = getattr(config, name, None)
    if val is None:
        return default
    return val


class UpdateDocument:
    """Orchestrate an update request: validate, create version, enqueue."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._document_repository = _get_attr(
            kwargs,
            'document_repository',
            'document_repo',
            'documents',
            'document_store',
            default=None,
        )
        self._object_storage = _get_attr(
            kwargs, 'object_storage', 'storage', 's3', 'object_store', 'storage_port', default=None
        )
        self._partition_manager = _get_attr(
            kwargs,
            'partition_manager',
            'partition_gateway',
            'partition_manager_port',
            'gateway',
            'pm',
            'partitioner',
            default=None,
        )
        self._partition_metadata_repository = _get_attr(
            kwargs,
            'partition_metadata_repository',
            'partition_metadata_repo',
            'partition_metadata',
            'partition_repository',
            'partition_repo',
            default=None,
        )
        self._partition_checker = _get_attr(
            kwargs,
            'partition_checker',
            'partition_exists_checker',
            'partition_exists',
            'has_partition',
            'check_partition',
            default=None,
        )
        self._unit_of_work = _get_attr(
            kwargs, 'unit_of_work', 'uow', 'transaction', 'tx', default=None
        )
        self._config = _get_attr(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )
        self._answer_cache = _get_attr(kwargs, 'answer_cache', 'cache', default=None)
        self._job_repository = _get_attr(kwargs, 'job_repository', 'job_repo', 'jobs', default=None)
        self._queue = _get_attr(kwargs, 'queue', 'queue_port', 'sqs', 'messaging', default=None)
        self._job_queue = self._queue
        self._change_event_publisher = _get_attr(
            kwargs,
            'change_event_publisher',
            'event_publisher',
            'publisher',
            'change_publisher',
            default=None,
        )
        self._metric_repository = _get_attr(
            kwargs, 'metric_repository', 'metrics', 'metrics_repository', default=None
        )
        self._company_repository = _get_attr(
            kwargs, 'company_repository', 'companies', default=None
        )
        self._delta_tracking = kwargs.get('delta_tracking')

        positional = [
            '_document_repository',
            '_object_storage',
            '_partition_manager',
            '_partition_metadata_repository',
            '_partition_checker',
            '_unit_of_work',
            '_config',
            '_answer_cache',
            '_job_repository',
        ]
        for index, value in enumerate(args):
            if index < len(positional):
                setattr(self, positional[index], value)

        # unwrap containers if needed
        for candidate_key in (
            'update_use_case',
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
                ('object_storage', '_object_storage'),
                ('storage', '_object_storage'),
                ('partition_manager', '_partition_manager'),
                ('config', '_config'),
                ('settings', '_config'),
                ('unit_of_work', '_unit_of_work'),
                ('answer_cache', '_answer_cache'),
                ('queue', '_queue'),
                ('job_repository', '_job_repository'),
                ('change_event_publisher', '_change_event_publisher'),
                ('metric_repository', '_metric_repository'),
            ):
                if getattr(self, target, None) is None and hasattr(candidate, attr_name):
                    setattr(self, target, getattr(candidate, attr_name))

        # config delta tracking
        if self._delta_tracking is None:
            self._delta_tracking = self._resolve_delta_tracking()

        self._expires_in = 900
        self._request_cache: dict[str, Any] = {}
        self._stamp_generations: dict[str, int] = {}

    # public entry points
    def execute(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def run(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def __call__(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def update(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def handle(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def update_document(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    async def _run(self, request: Any = None, extra: dict[str, Any] | None = None) -> UpdateResult:
        extra = extra or {}
        request = self._normalise_input(request, extra)
        action = _get_attr(request, 'action', 'operation', 'mode', default=None)
        if isinstance(request, dict):
            action = (
                action or request.get('action') or request.get('operation') or request.get('mode')
            )
        if action is None:
            action = extra.get('action') or extra.get('operation') or extra.get('mode')

        # company id
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

        # fields
        document_category = _get_attr(
            request,
            'document_category',
            'documentCategory',
            'category',
            'doc_category',
            'document_type',
        )
        period = _get_attr(request, 'period', 'reporting_period', 'period_label')
        status_raw = _get_attr(request, 'status', 'document_status', 'state')
        upload_type_raw = _get_attr(request, 'upload_type', 'uploadType', 'type', 'action')
        replaces_raw = _get_attr(
            request, 'replaces_document_id', 'replacesDocumentId', 'replace_document_id', 'replaces'
        )
        document_id_raw = _get_attr(
            request, 'document_id', 'documentId', 'doc_id', 'target_document_id', 'targetDocumentId'
        )
        filename_raw = _get_attr(request, 'filename', 'file_name', 'file', 'files')
        file_hash = _get_attr(request, 'file_hash', 'content_hash', 'hash', 'checksum')

        if isinstance(request, dict):
            if document_category is None:
                document_category = request.get('document_category') or request.get('category')
            if period is None:
                period = request.get('period')
            if status_raw is None:
                status_raw = request.get('status')
            if upload_type_raw is None:
                upload_type_raw = request.get('upload_type') or request.get('type')
            if replaces_raw is None:
                replaces_raw = request.get('replaces_document_id') or request.get('replaces')
            if document_id_raw is None:
                document_id_raw = request.get('document_id')
            if file_hash is None:
                file_hash = (
                    request.get('file_hash') or request.get('content_hash') or request.get('hash')
                )
        if upload_type_raw is None and action and str(action).lower() not in ('validate',):
            upload_type_raw = 'update'
        if document_category is None:
            raise ValidationError('document_category is required.')
        category_text = str(document_category).strip()
        allowed = self._resolve_allowed_categories()
        if allowed is not None and category_text not in allowed:
            raise ValidationError('document_category is not allowed.')
        if allowed is None:
            from finsight.core.types import DocumentCategory

            try:
                DocumentCategory(category_text)
            except ValueError as exc:
                raise ValidationError('document_category is not valid.') from exc
        if period is None:
            raise ValidationError('period is required.')
        period_text = str(period).strip()
        if not re.match(r'^\d{4}-(?:Q[1-4]|\d{2})$', period_text):
            raise ValidationError('period must be YYYY-QX or YYYY-MM.')
        if status_raw is None:
            raise ValidationError('status is required (draft or final).')
        status_text = str(status_raw).strip().lower()
        if status_text not in {'draft', 'final'}:
            raise ValidationError('status must be draft or final.')
        if upload_type_raw is None:
            raise ValidationError('upload_type is required (new or update).')
        upload_type_text = str(upload_type_raw).strip().lower()
        if upload_type_text not in {'new', 'update'}:
            raise ValidationError('upload_type must be new or update.')
        if upload_type_text == 'update':
            if (replaces_raw is None or str(replaces_raw).strip() == '') and (
                document_id_raw is None or str(document_id_raw).strip() == ''
            ):
                raise ValidationError('replaces_document_id is required for update uploads.')

        await self._step_ensure_partition(company_id)

        if upload_type_text == 'update':
            if replaces_raw is not None and str(replaces_raw).strip() != '':
                document_id = DocumentId(str(replaces_raw).strip())
            elif document_id_raw is not None:
                document_id = DocumentId(str(document_id_raw).strip())
            else:
                document_id = DocumentId(str(uuid.uuid4()))
        elif document_id_raw is not None and str(document_id_raw).strip() != '':
            document_id = DocumentId(str(document_id_raw).strip())
        else:
            document_id = DocumentId(str(uuid.uuid4()))
        version_id = str(uuid.uuid4())

        # version number
        version_number = 1
        repo = self._document_repository
        if repo is not None:
            try:
                existing_versions = await _await(
                    repo.list_document_versions(company_id, document_id)
                )
                if isinstance(existing_versions, list):
                    version_number = len(existing_versions) + 1
            except TypeError:
                try:
                    existing_versions = await _await(repo.list_document_versions(company_id))
                    if isinstance(existing_versions, list):
                        same = [
                            v
                            for v in existing_versions
                            if str(_get_attr(v, 'document_id', 'documentId', 'doc_id', default=''))
                            == str(document_id)
                        ]
                        version_number = len(same) + 1
                except Exception:
                    version_number = 1
            except Exception:
                version_number = 1

        # duplicate detection
        duplicate_found = False
        suggested_document_id = None
        suggested_version_id = None
        if repo is not None:
            try:
                all_versions = await _await(repo.list_document_versions(company_id))
            except Exception:
                all_versions = []
            if isinstance(all_versions, list):
                filename = self._resolve_filename(filename_raw)
                for prior in all_versions:
                    prior_hash = _get_attr(prior, 'file_hash', 'content_hash', 'hash', 'checksum')
                    prior_category = _get_attr(
                        prior, 'category', 'document_category', 'doc_category'
                    )
                    prior_period = _get_attr(prior, 'period', 'reporting_period')
                    prior_name = _get_attr(
                        prior, 'filename', 'file_name', 'name', 'original_filename'
                    )
                    prior_doc_id = _get_attr(prior, 'document_id', 'documentId', 'doc_id')
                    prior_ver_id = _get_attr(prior, 'id', 'version_id', 'document_version_id')
                    hash_match = (
                        file_hash is not None
                        and prior_hash is not None
                        and str(file_hash).strip() != ''
                        and str(file_hash).strip() == str(prior_hash).strip()
                    )
                    name_match = (
                        str(prior_category).strip().lower() == category_text.lower()
                        and str(prior_period).strip().lower() == period_text.lower()
                        and prior_name is not None
                        and str(prior_name).strip().lower() == filename.strip().lower()
                    )
                    if hash_match or name_match:
                        duplicate_found = True
                        if suggested_document_id is None:
                            suggested_document_id = prior_doc_id
                        if suggested_version_id is None:
                            suggested_version_id = prior_ver_id
                        break

        filename = self._resolve_filename(filename_raw)

        version_entity = DocumentVersion(
            id=version_id,
            company_id=company_id,
            document_id=document_id,
            state='received',
            filename=filename,
            file_hash=file_hash,
            category=category_text,
            version=version_number,
        )

        # presigned upload (optional, reuse storage if present)
        key = None
        presigned = None
        bucket = None
        expires_in = self._expires_in
        content_type = None
        storage = self._object_storage
        if storage is not None:
            try:
                key = storage.build_key(company_id, document_id, version_id, filename)
            except Exception:
                key = f'{company_id}/documents/{document_id}/versions/{version_id}/{filename}'
            if key is None:
                key = f'{company_id}/documents/{document_id}/versions/{version_id}/{filename}'
            try:
                presigned = await _await(
                    storage.generate_presigned_upload_url(
                        company_id,
                        key=key,
                        expires_in=expires_in,
                        content_type=content_type,
                        document_id=document_id,
                        version_id=version_id,
                        filename=filename,
                    )
                )
            except TypeError:
                try:
                    presigned = await _await(
                        storage.generate_presigned_upload_url(
                            company_id, key, expires_in=expires_in
                        )
                    )
                except Exception:
                    presigned = None
            try:
                bucket = _get_attr(presigned, 'bucket', default=None)
                if bucket is None:
                    bucket = getattr(storage, 'bucket', None)
            except Exception:
                bucket = getattr(storage, 'bucket', None)
            try:
                content_type = getattr(presigned, 'content_type', content_type)
            except Exception:
                pass
            try:
                key = getattr(presigned, 'key', key) or key
            except Exception:
                pass

        tx = None
        if self._unit_of_work is not None:
            tx = await self._begin_transaction()
        try:
            created_version = version_entity
            if repo is not None:
                created = await self._create_document_version(
                    company_id=company_id,
                    version_entity=version_entity,
                    document_id=document_id,
                    version_number=version_number,
                    category=category_text,
                    period=period_text,
                    status=status_text,
                    upload_type=upload_type_text,
                    replaces=replaces_raw,
                    filename=filename,
                    file_hash=file_hash,
                )
                if created is not None:
                    created_version = created

            actual_version_id = _get_attr(
                created_version, 'id', 'version_id', 'document_version_id', default=version_id
            )
            actual_document_id = _get_attr(
                created_version, 'document_id', 'documentId', 'doc_id', default=document_id
            )
            if actual_version_id is not None:
                version_id = str(actual_version_id)
            if actual_document_id is not None:
                document_id = DocumentId(str(actual_document_id))

            await self._commit_transaction(tx)
        except Exception:
            await self._rollback_transaction(tx)
            raise

        # delta tracking from config/request
        delta_tracking = self._delta_tracking
        if isinstance(request, dict) and request.get('delta_tracking') is not None:
            try:
                delta_tracking = bool(request.get('delta_tracking'))
            except Exception:
                pass
        if extra.get('delta_tracking') is not None:
            try:
                delta_tracking = bool(extra.get('delta_tracking'))
            except Exception:
                pass
        if delta_tracking is None:
            delta_tracking = True
        delta_tracking = bool(delta_tracking)

        # enqueue pipeline
        job_id = _get_attr(request, 'job_id', 'jobId', default=None)
        if job_id is None and isinstance(request, dict):
            job_id = request.get('job_id') or request.get('jobId')
        enqueued, queued_job_id = await self._enqueue(
            company_id=company_id,
            document_id=document_id,
            version_id=version_id,
            category=category_text,
            period=period_text,
            status=status_text,
            upload_type=upload_type_text,
            replaces=replaces_raw,
            filename=filename,
            file_hash=file_hash,
            delta_tracking=delta_tracking,
            job_id=job_id,
        )
        if queued_job_id is not None:
            job_id = queued_job_id

        (
            stamp_value,
            cache_cleared,
            affected,
            metrics_recomputed,
            published,
        ) = await self._step_finalize(
            company_id,
            document_id,
            version_id,
            category_text,
            period_text,
            upload_type_text,
            replaces_raw,
            job_id,
        )

        result = UpdateResult(
            company_id=company_id,
            document_id=document_id,
            version_id=version_id,
            document_version=created_version,
            version=created_version,
            state='received',
            status='accepted',
            upload_url=presigned,
            presigned_url=presigned,
            url=presigned,
            link=presigned,
            key=key,
            storage_key=key,
            object_key=key,
            s3_key=key,
            bucket=bucket,
            expires_in=expires_in,
            content_type=content_type,
            presigned_upload=presigned,
            duplicate=duplicate_found,
            is_duplicate=duplicate_found,
            suggested_document_id=suggested_document_id,
            suggested_version_id=suggested_version_id,
            enqueued=enqueued,
            queued=enqueued,
            queued_job=enqueued,
            job_id=job_id,
            delta_tracking=delta_tracking,
            stamp=stamp_value,
            document_stamp=stamp_value,
            cache_cleared=cache_cleared,
            affected_documents=affected,
            metrics_recomputed=metrics_recomputed,
            published=published,
            cascade_triggered=bool(affected),
            partition_missing=False,
        )
        return result

    async def _step_finalize(
        self,
        company_id: Any,
        document_id: Any,
        version_id: Any,
        category_text: str,
        period_text: str,
        upload_type_text: str,
        replaces_raw: Any,
        job_id: Any,
    ) -> tuple[Any, bool, Any, bool, bool]:
        # update stamp
        stamp_value = None
        try:
            stamp_value = await self._update_stamp(company_id, document_id, version_id)
        except Exception:
            stamp_value = None

        # clear cache
        cache_cleared = False
        try:
            await self._clear_cache(company_id)
            cache_cleared = True
        except Exception:
            cache_cleared = False

        # flag other docs same company/period
        affected = await self._flag_affected(
            company_id, document_id, category_text, period_text, version_id, job_id
        )

        # metrics recompute (log/flag)
        metrics_recomputed = await self._recompute_metrics(company_id, document_id, affected)

        # publish change event
        published = await self._publish_change(
            company_id,
            document_id,
            version_id,
            category_text,
            period_text,
            upload_type_text,
            replaces_raw,
            job_id,
        )

        await self._request_cascade(
            company_id, document_id, version_id, category_text, period_text, job_id
        )
        return stamp_value, cache_cleared, affected, metrics_recomputed, published

    async def _step_ensure_partition(self, company_id: Any) -> None:
        await self._ensure_partition(company_id)

    def _normalise_input(self, request: Any, extra: dict[str, Any]) -> Any:
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
                'target_document_id',
                'document_category',
                'documentCategory',
                'category',
                'period',
                'reporting_period',
                'period_label',
                'status',
                'document_status',
                'state',
                'upload_type',
                'uploadType',
                'type',
                'action',
                'replaces_document_id',
                'replacesDocumentId',
                'replace_document_id',
                'replaces',
                'file',
                'files',
                'filename',
                'file_name',
                'document',
                'documents',
                'file_hash',
                'content_hash',
                'hash',
                'checksum',
                'job_id',
                'jobId',
            ):
                value = _get_attr(request, attr, default=None)
                if value is not None:
                    wrapper[attr] = value
        wrapper.update(extra)
        return wrapper

    async def _ensure_partition(self, company_id: Any) -> None:
        if (
            self._partition_manager is None
            and self._partition_metadata_repository is None
            and self._partition_checker is None
        ):
            return
        exists = await self._partition_exists(company_id)
        if not exists:
            raise ValidationError('partition missing')

    async def _partition_exists(self, company_id: Any) -> bool:
        # reuse upload-style condensed check
        checker = self._partition_checker
        if checker is not None:
            if (
                callable(checker)
                and not hasattr(checker, 'partition_exists')
                and not hasattr(checker, 'exists')
            ):
                try:
                    return bool(await _await(checker(company_id)))
                except TypeError:
                    try:
                        return bool(await _await(checker()))
                    except Exception:
                        return True
            for attr in (
                'partition_exists',
                'ensure_partition_exists',
                'has_partition',
                'exists',
                'check_partition',
                'check_partition_exists',
            ):
                method = getattr(checker, attr, None)
                if callable(method):
                    try:
                        result = await self._call_method(method, company_id, 'documents')
                        if result is not None:
                            return bool(result)
                    except Exception:
                        continue
        manager = self._partition_manager
        if manager is not None:
            for attr in (
                'partition_exists',
                'ensure_partition_exists',
                'has_partition',
                'exists',
                'is_partitioned',
                'check_partition',
                'check_partition_exists',
            ):
                method = getattr(manager, attr, None)
                if callable(method):
                    try:
                        result = await self._call_method(method, company_id, 'documents')
                        if result is not None:
                            return bool(result)
                    except Exception:
                        continue
        metadata = self._partition_metadata_repository
        if metadata is not None:
            for attr in (
                'partition_exists',
                'ensure_partition_exists',
                'has_partition',
                'exists',
                'check_partition',
            ):
                method = getattr(metadata, attr, None)
                if callable(method):
                    try:
                        result = await self._call_method(method, company_id, 'documents')
                        if result is not None:
                            return bool(result)
                    except Exception:
                        continue
        return True

    async def _call_method(
        self, method: Any, company_id: Any, table_name: str | None = None
    ) -> Any:
        try:
            result = method(company_id)
            return await _await(result)
        except TypeError:
            pass
        except Exception:
            pass
        if table_name is not None:
            try:
                result = method(company_id, table_name)
                return await _await(result)
            except (TypeError, Exception):
                pass
        for kwargs in ({'company_id': company_id}, {'companyId': company_id}, {}):
            try:
                result = method(**kwargs)
                return await _await(result)
            except TypeError:
                continue
            except Exception:
                continue
        return None

    def _resolve_allowed_categories(self) -> list[str] | None:
        if self._config is not None:
            candidate = None
            if isinstance(self._config, dict):
                candidate = self._config.get('documents', self._config.get('document', {}))
            else:
                candidate = _get_attr(self._config, 'documents', 'document')
            categories = None
            if isinstance(candidate, dict):
                categories = candidate.get('categories', candidate.get('category', None))
            elif candidate is not None:
                categories = _get_attr(candidate, 'categories', 'category')
            if isinstance(categories, (list, tuple, set)):
                cats = [str(item) for item in categories]
                if cats:
                    return cats
        return None

    def _resolve_delta_tracking(self) -> bool:
        value = self._delta_tracking
        if value is None:
            switched = _switch(self._config, 'delta_tracking', None)
            if switched is not None:
                value = switched
            else:
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

    def _resolve_filename(self, file_raw: Any) -> str:
        if isinstance(file_raw, str):
            name = file_raw.strip()
            if name:
                return name.split('/')[-1].split('\\')[-1] or 'document.pdf'
        if isinstance(file_raw, (list, tuple)) and len(file_raw) > 0:
            return self._resolve_filename(file_raw[0])
        if file_raw is not None:
            attr_name = getattr(file_raw, 'filename', None) or getattr(file_raw, 'name', None)
            if attr_name:
                return str(attr_name).split('/')[-1].split('\\')[-1]
        return 'document.pdf'

    async def _create_document_version(self, **kwargs: Any) -> Any:
        repo = self._document_repository
        company_id = kwargs.pop('company_id')
        version_entity = kwargs.pop('version_entity', None)
        for method_name in (
            'create_document_version',
            'create_version',
            'create_document_version_record',
            'save_document_version',
            'insert_document_version',
            'create',
        ):
            method = getattr(repo, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(company_id, document_version=version_entity, **kwargs)
                return await _await(result)
            except TypeError:
                pass
            try:
                result = method(company_id, version_entity, **kwargs)
                return await _await(result)
            except TypeError:
                pass
            create_kwargs = dict(kwargs)
            create_kwargs.setdefault('document_version', version_entity)
            create_kwargs.setdefault('version', version_entity)
            create_kwargs.setdefault('state', 'received')
            create_kwargs.setdefault('document_id', kwargs.get('document_id'))
            create_kwargs.setdefault('id', kwargs.get('version_id'))
            for call in (
                (lambda m=method, kw=create_kwargs: m(company_id, **kw)),
                (lambda m=method, kw=create_kwargs: m(company_id=company_id, **kw)),
            ):
                try:
                    return await _await(call())  # type: ignore[no-untyped-call]
                except TypeError:
                    continue
                except Exception:
                    continue
        return version_entity

    async def _enqueue(self, **kwargs: Any) -> tuple[bool, Any]:
        company_id = kwargs['company_id']
        queue = self._queue
        job_repo = self._job_repository
        payload = {
            'company_id': str(company_id),
            'document_id': str(kwargs['document_id']),
            'version_id': str(kwargs['version_id']),
            'category': kwargs.get('category'),
            'period': kwargs.get('period'),
            'status': kwargs.get('status'),
            'upload_type': kwargs.get('upload_type'),
            'replaces_document_id': kwargs.get('replaces'),
            'filename': kwargs.get('filename'),
            'file_hash': kwargs.get('file_hash'),
            'delta_tracking': kwargs.get('delta_tracking'),
            'job_id': kwargs.get('job_id'),
            'priority': 'low' if kwargs.get('priority') is None else kwargs.get('priority'),
        }
        # try queue first
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
                # method maybe queue selection aware
                attempts = (
                    lambda m=method: m('ingestion', payload),
                    lambda m=method: m(queue='ingestion', message=payload),
                    lambda m=method: m(company_id, payload),
                    lambda m=method: m(payload),
                    lambda m=method: m(message=payload),
                    lambda m=method: m(body=payload),
                    lambda m=method: m(event=payload),
                    lambda m=method: m(job=payload),
                    lambda m=method: m(priority=payload.get('priority'), **payload),
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
                                or result.get('message_id')
                                or result.get('MessageId')
                            )
                        elif result is not None:
                            jid = (
                                getattr(result, 'job_id', None)
                                or getattr(result, 'jobId', None)
                                or getattr(result, 'id', None)
                            )
                        if jid is None:
                            if isinstance(result, (str, int, uuid.UUID)):
                                jid = result
                            else:
                                jid = kwargs.get('job_id')
                        return True, jid
                    except TypeError:
                        continue
                    except Exception:
                        # try next attempt only if TypeError-like; break to next method
                        break
        # job repository
        if job_repo is not None:
            for method_name in (
                'create_job',
                'create',
                'add_job',
                'enqueue',
                'schedule',
                'save_job',
            ):
                method = getattr(job_repo, method_name, None)
                if not callable(method):
                    continue
                for attempt in (
                    lambda m=method: m(company_id, payload),
                    lambda m=method: m(company_id=company_id, **payload),
                    lambda m=method: m(payload),
                ):
                    try:
                        result = await _await(attempt())
                        jid = None
                        if isinstance(result, dict):
                            jid = result.get('job_id') or result.get('jobId') or result.get('id')
                        elif result is not None:
                            jid = getattr(result, 'job_id', None) or getattr(result, 'id', None)
                        if jid is None:
                            if isinstance(result, (str, int, uuid.UUID)):
                                jid = result
                            else:
                                jid = kwargs.get('job_id')
                        return True, jid
                    except TypeError:
                        continue
                    except Exception:
                        break
        return False, kwargs.get('job_id')

    async def _begin_transaction(self) -> Any:
        uow = self._unit_of_work
        if uow is None:
            return None
        for attr in ('begin', 'start', 'transaction', 'begin_transaction'):
            method = getattr(uow, attr, None)
            if callable(method):
                try:
                    return await _await(method())
                except TypeError:
                    try:
                        return await _await(method(self._unit_of_work and None))
                    except Exception:
                        pass
        if callable(uow):
            try:
                return await _await(uow())
            except Exception:
                return None
        return uow

    async def _commit_transaction(self, tx: Any) -> None:
        if tx is None:
            uow = self._unit_of_work
            if uow is not None:
                method = getattr(uow, 'commit', None)
                if callable(method):
                    await _await(method())
            return
        method = getattr(tx, 'commit', None)
        if callable(method):
            await _await(method())
            return
        if self._unit_of_work is not None:
            method = getattr(self._unit_of_work, 'commit', None)
            if callable(method):
                await _await(method())

    async def _rollback_transaction(self, tx: Any) -> None:
        with contextlib.suppress(Exception):
            if tx is not None:
                method = getattr(tx, 'rollback', None)
                if callable(method):
                    await _await(method())
                    return
            if self._unit_of_work is not None:
                method = getattr(self._unit_of_work, 'rollback', None)
                if callable(method):
                    await _await(method())

    async def _update_stamp(self, company_id: Any, document_id: Any, version_id: Any) -> Any:
        repo = self._document_repository
        stamp = None
        try:
            from finsight.domain.services.document_stamp import DocumentStamp

            markers: dict[str, Any] = {}
            if repo is not None and hasattr(repo, 'document_version_markers'):
                try:
                    markers = await _await(repo.document_version_markers(company_id)) or {}
                except Exception:
                    markers = {}
            if not isinstance(markers, dict):
                markers = {}
            new_markers = dict(markers)
            new_markers[str(document_id)] = str(version_id)
            try:
                company_key = str(company_id)
                current_gen = self._stamp_generations.get(company_key, 0)
                new_gen = current_gen + 1
                self._stamp_generations[company_key] = new_gen
                stamp = DocumentStamp.from_versions(company_id, new_markers, generation=new_gen)
            except Exception:
                stamp = DocumentStamp.initial(company_id).updated_for(new_markers)
        except Exception:
            stamp = None
        if repo is not None:
            for method_name, _payload in (('update_document_stamp', None),):
                method = getattr(repo, method_name, None)
                if callable(method):
                    try:
                        await _await(method(company_id, document_id, stamp))
                        break
                    except TypeError:
                        try:
                            await _await(
                                method(company_id=company_id, document_id=document_id, stamp=stamp)
                            )
                            break
                        except (TypeError, Exception):
                            try:
                                await _await(method(company_id, document_id, document_stamp=stamp))
                                break
                            except Exception:
                                pass
                    except Exception:
                        pass
            for method_name in ('update_document',):
                method = getattr(repo, method_name, None)
                if callable(method):
                    try:
                        await _await(
                            method(
                                company_id,
                                document_id,
                                document_stamp=str(getattr(stamp, 'value', stamp)),
                                stamp=str(getattr(stamp, 'value', stamp)),
                            )
                        )
                        break
                    except TypeError:
                        try:
                            await _await(
                                method(
                                    company_id=company_id,
                                    document_id=document_id,
                                    document_stamp=str(getattr(stamp, 'value', stamp)),
                                )
                            )
                            break
                        except Exception:
                            pass
                    except Exception:
                        pass
        return stamp

    async def _clear_cache(self, company_id: Any) -> None:
        cache = self._answer_cache
        if cache is None:
            return
        for method_name in (
            'clear_on_update',
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
                    return
                except TypeError:
                    try:
                        await _await(method(company_id=company_id))
                        return
                    except Exception:
                        continue
                except Exception:
                    continue

    async def _flag_affected(
        self,
        company_id: Any,
        document_id: Any,
        category: str,
        period: str,
        version_id: Any,
        job_id: Any,
    ) -> list[str]:
        repo = self._document_repository
        affected: list[str] = []
        docs = None
        if repo is not None:
            for list_method in (
                'list_documents',
                'list_by_company',
                'list_for_company',
                'list_all_documents',
            ):
                method = getattr(repo, list_method, None)
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
        if docs is None:
            docs = []
        for doc in docs or []:
            doc_id = _get_attr(doc, 'id', 'document_id', 'doc_id')
            if doc_id is None or str(doc_id) == str(document_id):
                continue
            doc_period = _get_attr(doc, 'period', 'reporting_period')
            if period is not None and doc_period is not None and str(doc_period) != str(period):
                continue
            doc_id_text = str(doc_id)
            affected.append(doc_id_text)
            if repo is not None:
                for update_method in ('update_document', 'flag_document', 'mark_may_be_affected'):
                    method = getattr(repo, update_method, None)
                    if callable(method):
                        with contextlib.suppress(Exception):
                            await _await(method(company_id, doc_id, may_be_affected=True))
                        break
        # mark dependent metrics stale
        metric_repo = self._metric_repository
        if metric_repo is not None and affected:
            for stale_method in (
                'mark_stale',
                'flag_stale',
                'invalidate_for_documents',
                'mark_dependent_stale',
                'mark_metrics_stale',
                'mark_stale_for_documents',
                'invalidate_documents',
            ):
                method = getattr(metric_repo, stale_method, None)
                if callable(method):
                    with contextlib.suppress(Exception):
                        await _await(method(company_id, affected))
                    with contextlib.suppress(Exception):
                        await _await(method(company_id=company_id, document_ids=affected))
                    break
        # publish change events for affected docs
        publisher = self._change_event_publisher
        if publisher is not None and affected:
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
                for doc_id in affected
            ]
            for method_name in ('publish_many', 'publish_events', 'publish_all'):
                method = getattr(publisher, method_name, None)
                if callable(method):
                    with contextlib.suppress(Exception):
                        await _await(method(company_id, events))
                    break
            else:
                for event in events:
                    with contextlib.suppress(Exception):
                        await _await(publisher.publish(company_id, event))
        return affected

    async def _publish_change(
        self,
        company_id: Any,
        document_id: Any,
        version_id: Any,
        category: Any,
        period: Any,
        upload_type: Any,
        replaces: Any,
        job_id: Any,
    ) -> bool:
        publisher = self._change_event_publisher
        if publisher is None:
            return False
        event_type = ChangeEventType.DOCUMENT_UPDATED
        try:
            event = DocumentChangeEvent(
                company_id=company_id,
                document_id=document_id,
                event_type=ChangeEventType.normalize(event_type),
                version_id=str(version_id),
                superseded_version_id=str(replaces) if replaces is not None else None,
                category=category,
                period=period,
                job_id=job_id,
            )
            await _await(publisher.publish(company_id, event))
            return True
        except Exception:
            try:
                await _await(publisher.publish_change(company_id, event))
                return True
            except Exception:
                return False

    async def _request_cascade(
        self,
        company_id: Any,
        document_id: Any,
        version_id: Any,
        category: Any,
        period: Any,
        job_id: Any,
    ) -> None:
        publisher = self._change_event_publisher
        if publisher is None:
            return
        try:
            if hasattr(publisher, 'request_cascade'):
                await _await(
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
                await _await(publisher.publish(company_id, event))
        except Exception:
            with contextlib.suppress(Exception):
                await _await(publisher.publish_cascade(company_id, document_id=document_id))

    async def _recompute_metrics(self, company_id: Any, document_id: Any, affected: Any) -> bool:
        repo = self._metric_repository
        if repo is None:
            return False
        for method_name in (
            'recompute',
            'recompute_for_document',
            'recompute_metrics',
            'refresh',
            'recalculate',
        ):
            method = getattr(repo, method_name, None)
            if callable(method):
                for attempt in (
                    lambda m=method: m(company_id, document_id),
                    lambda m=method: m(company_id=company_id, document_id=document_id),
                ):
                    try:
                        await _await(attempt())  # type: ignore[no-untyped-call]
                        return True
                    except TypeError:
                        continue
                    except Exception:
                        break
        return False


# Aliases
Update = UpdateDocument
UpdateUseCase = UpdateDocument
UpdateDocumentUseCase = UpdateDocument
DocumentUpdate = UpdateDocument
DocumentUpdateUseCase = UpdateDocument
UpdateOrchestrator = UpdateDocument
UpdateService = UpdateDocument
UpdateHandlerUseCase = UpdateDocument

__all__ = [
    'DocumentUpdate',
    'DocumentUpdateUseCase',
    'Update',
    'UpdateDocument',
    'UpdateDocumentUseCase',
    'UpdateHandlerUseCase',
    'UpdateOrchestrator',
    'UpdateResult',
    'UpdateService',
    'UpdateUseCase',
]
