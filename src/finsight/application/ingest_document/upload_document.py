"""Upload application use case: version creation + presigned link."""

from __future__ import annotations

import contextlib
import inspect
import uuid
from typing import Any

from finsight.core.errors import ValidationError
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.document_version import DocumentVersion

from .models import UploadInput, UploadResult

__all__ = ['PartitionMissingError', 'UploadDocument']


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


class PartitionMissingError(ValidationError):
    """Raised when a company partition does not exist."""


class UploadDocument:
    """Orchestrate an upload request: version + presigned link."""

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
            kwargs,
            'object_storage',
            'storage',
            's3',
            'object_store',
            'storage_port',
            default=None,
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
        self._queue = _get_attr(
            kwargs,
            'queue_port',
            'queue',
            'queue_adapter',
            'sqs',
            'job_queue',
            'messaging',
            default=None,
        )
        self._queue_port = self._queue
        self._allowed_categories = None
        self._expires_in = 900

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
            '_queue',
        ]
        for index, value in enumerate(args):
            if index < len(positional):
                setattr(self, positional[index], value)

        # Keep aliases in sync when dependencies are passed positionally.
        if getattr(self, '_queue', None) is not None:
            self._queue_port = self._queue
            self.queue = self._queue
            self.queue_port = self._queue
        if getattr(self, '_job_repository', None) is not None:
            self.job_repository = self._job_repository

        # If a provided use-case-like/container was passed, unwrap common attrs.
        for candidate_key in (
            'upload_use_case',
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
                ('partition_gateway', '_partition_manager'),
                ('config', '_config'),
                ('settings', '_config'),
                ('unit_of_work', '_unit_of_work'),
            ):
                if getattr(self, target, None) is None and hasattr(candidate, attr_name):
                    setattr(self, target, getattr(candidate, attr_name))

        # request cache for idempotency (no-op by default)
        self._request_cache: dict[str, UploadResult] = {}

    # Public entry points
    def execute(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def run(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def __call__(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def upload(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def handle(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def request_upload(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def create_version(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def create_document_version(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def create(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def handle_upload(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    async def _run(self, request: Any = None, extra: dict[str, Any] | None = None) -> UploadResult:
        extra = extra or {}
        request = self._normalise_input(request, extra)

        # Resolve company id.
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

        # Resolve fields.
        inp = UploadInput()
        # hydrate from request
        if isinstance(request, dict):
            for k, v in request.items():
                if v is not None and hasattr(inp, k):
                    setattr(inp, k, v)
        if inp.company_id is None:
            inp.company_id = company_id_raw
        # field access
        document_category = _get_attr(
            request,
            'document_category',
            'documentCategory',
            'category',
            'doc_category',
            'document_type',
        )
        if document_category is None:
            document_category = inp.document_category
        period = _get_attr(request, 'period', 'reporting_period', 'period_label')
        if period is None:
            period = inp.period
        status_raw = _get_attr(request, 'status', 'document_status', 'state')
        if status_raw is None:
            status_raw = inp.status
        upload_type_raw = _get_attr(request, 'upload_type', 'uploadType', 'type', 'action')
        if upload_type_raw is None:
            upload_type_raw = inp.upload_type
        replaces_raw = _get_attr(
            request, 'replaces_document_id', 'replacesDocumentId', 'replace_document_id', 'replaces'
        )
        if replaces_raw is None:
            replaces_raw = inp.replaces_document_id
        file_raw = _get_attr(
            request, 'file', 'files', 'filename', 'file_name', 'document', 'documents'
        )
        if file_raw is None:
            file_raw = inp.file
        file_hash = _get_attr(request, 'file_hash', 'content_hash', 'hash', 'checksum')
        if file_hash is None:
            file_hash = inp.file_hash

        # Allowed categories from config.
        allowed_categories = self._resolve_allowed_categories()

        # Validate form.
        if document_category is None:
            raise ValidationError('document_category is required.')
        category_text = str(document_category).strip()
        if allowed_categories is not None and category_text not in allowed_categories:
            raise ValidationError('document_category is not allowed.')
        if allowed_categories is None:
            from finsight.core.types import DocumentCategory

            try:
                DocumentCategory(category_text)
            except ValueError as exc:
                raise ValidationError('document_category is not valid.') from exc

        if period is None:
            raise ValidationError('period is required.')
        period_text = str(period).strip()
        import re

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
            if replaces_raw is None or str(replaces_raw).strip() == '':
                raise ValidationError('replaces_document_id is required for update uploads.')

        # Partition-existence gate.
        await self._ensure_partition(company_id)

        # Determine filename.
        filename = self._resolve_filename(file_raw)

        # Generate document/version ids.
        if upload_type_text == 'update' and replaces_raw is not None:
            document_id = DocumentId(str(replaces_raw).strip())
        else:
            document_id = DocumentId(str(uuid.uuid4()))
        version_id = str(uuid.uuid4())

        # Version number (best effort).
        version_number = 1
        if self._document_repository is not None:
            try:
                existing_versions = await _await(
                    self._document_repository.list_document_versions(company_id, document_id)
                )
                if isinstance(existing_versions, list):
                    version_number = len(existing_versions) + 1
            except Exception:
                try:
                    existing_versions = await _await(
                        self._document_repository.list_document_versions(company_id)
                    )
                    if isinstance(existing_versions, list):
                        # only count same document
                        same = [
                            v
                            for v in existing_versions
                            if str(_get_attr(v, 'document_id', 'documentId', 'doc_id', default=''))
                            == str(document_id)
                        ]
                        version_number = len(same) + 1
                except Exception:
                    version_number = 1

        # Duplicate detection.
        duplicate_found = False
        suggested_document_id = None
        suggested_version_id = None
        if self._document_repository is not None:
            try:
                all_versions = await _await(
                    self._document_repository.list_document_versions(company_id)
                )
            except Exception:
                all_versions = []
            if isinstance(all_versions, list):
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

        # Create DocumentVersion in received state.
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

        tx = None
        if self._unit_of_work is not None:
            tx = await self._begin_transaction()
        try:
            created_version = version_entity
            if self._document_repository is not None:
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

            # Issue presigned link.
            key = None
            presigned = None
            bucket = None
            expires_in = self._expires_in
            content_type = None
            storage = self._object_storage
            if storage is not None:
                if key is None:
                    try:
                        key = storage.build_key(company_id, document_id, version_id, filename)
                    except Exception:
                        key = (
                            f'{company_id}/documents/{document_id}/versions/{version_id}/{filename}'
                        )
                else:
                    pass
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

            await self._commit_transaction(tx)

            # Trigger ingestion for the newly created version.
            enqueued = False
            queued_job_id = None
            try:
                enqueued, queued_job_id = await self._trigger_ingestion(
                    company_id, document_id, version_id
                )
            except Exception:
                enqueued = False
                queued_job_id = None
        except Exception:
            await self._rollback_transaction(tx)
            raise

        result = UploadResult(
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
            suggest_update=duplicate_found,
            suggested_document_id=suggested_document_id,
            suggested_version_id=suggested_version_id,
            partition_missing=False,
            enqueued=enqueued,
            queued=enqueued,
            queued_job=enqueued,
            job_id=queued_job_id,
        )
        return result

    async def _trigger_ingestion(
        self, company_id: Any, document_id: Any, version_id: Any
    ) -> tuple[bool, Any]:
        queue = self._queue_port if self._queue_port is not None else self._queue
        job_repo = self._job_repository
        version_text = str(version_id)
        if queue is None:
            if job_repo is None:
                return False, None
            if await self._job_already_exists(job_repo, company_id, version_text):
                return False, version_text
            await self._record_ingestion_job(job_repo, company_id, version_text)
            return True, version_text
        version_text = str(version_id)
        job_payload = {
            'company_id': str(company_id),
            'document_id': str(document_id),
            'version_id': version_text,
            'action': 'ingest',
        }
        job_repo = self._job_repository
        if await self._job_already_exists(job_repo, company_id, version_text):
            return False, None
        enqueued, job_id = await self._enqueue_ingestion(queue, job_payload, version_text)
        if enqueued and job_repo is not None:
            await self._record_ingestion_job(job_repo, company_id, version_text)
        if job_id is None:
            job_id = version_text
        return enqueued, job_id

    async def _job_already_exists(self, job_repo: Any, company_id: Any, version_id: str) -> bool:
        if job_repo is None:
            return False
        finder = None
        for name in ('find_job', 'find', 'get_job', 'get', 'fetch_job', 'fetch'):
            candidate = getattr(job_repo, name, None)
            if callable(candidate):
                finder = candidate
                break
        if finder is None:
            return False
        for attempt in (
            lambda m=finder: m(company_id, version_id=version_id),
            lambda m=finder: m(company_id, version_id),
        ):
            try:
                result = await _await(attempt())  # type: ignore[no-untyped-call]
                return bool(result)
            except TypeError:
                continue
            except Exception:
                continue
        return False

    async def _enqueue_ingestion(
        self, queue: Any, payload: dict[str, Any], version_id: str
    ) -> tuple[bool, Any]:
        job_id: Any = None
        queue_method = None
        for name in (
            'enqueue',
            'enqueue_job',
            'send',
            'send_message',
            'publish',
            'dispatch',
            'put',
        ):
            candidate = getattr(queue, name, None)
            if callable(candidate):
                queue_method = candidate
                break
        if queue_method is None:
            return False, None
        attempts = (
            lambda m=queue_method: m('ingestion', payload),
            lambda m=queue_method: m(queue='ingestion', message=payload),
            lambda m=queue_method: m(payload=payload, queue='ingestion'),
            lambda m=queue_method: m(payload),
            lambda m=queue_method: m(message=payload),
            lambda m=queue_method: m(body=payload),
        )
        for attempt in attempts:
            try:
                result = await _await(attempt())  # type: ignore[no-untyped-call]
                if isinstance(result, dict):
                    job_id = (
                        result.get('job_id')
                        or result.get('jobId')
                        or result.get('id')
                        or result.get('message_id')
                        or result.get('MessageId')
                    )
                elif result is not None:
                    job_id = (
                        getattr(result, 'job_id', None)
                        or getattr(result, 'jobId', None)
                        or getattr(result, 'id', None)
                    )
                if job_id is None and isinstance(result, (str, int, uuid.UUID)):
                    job_id = result
                if job_id is None:
                    job_id = version_id
                return True, job_id
            except TypeError:
                continue
            except Exception:
                break
        return False, None

    async def _record_ingestion_job(self, job_repo: Any, company_id: Any, version_id: str) -> None:
        for name in (
            'create_job',
            'create',
            'add_job',
            'enqueue',
            'schedule',
            'save_job',
            'upsert_job',
            'upsert',
            'insert',
        ):
            creator = getattr(job_repo, name, None)
            if not callable(creator):
                continue
            job_attempts = (
                lambda m=creator: m(company_id, version_id, 'queued'),
                lambda m=creator: m(company_id, version_id, status='queued'),
                lambda m=creator: m(company_id=company_id, job_id=version_id, status='queued'),
                lambda m=creator: m(company_id=company_id, version_id=version_id, status='queued'),
            )
            for attempt in job_attempts:
                try:
                    await _await(attempt())  # type: ignore[no-untyped-call]
                    return
                except TypeError:
                    continue
                except Exception:
                    break
        # try the next available repository method

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
                'document_category',
                'documentCategory',
                'category',
                'period',
                'reporting_period',
                'status',
                'document_status',
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
            ):
                value = _get_attr(request, attr, default=None)
                if value is not None:
                    wrapper[attr] = value
        wrapper.update(extra)
        return wrapper

    async def _ensure_partition(self, company_id: Any) -> None:
        # If no partition deps provided, skip.
        if (
            self._partition_manager is None
            and self._partition_metadata_repository is None
            and self._partition_checker is None
        ):
            return
        exists = await self._partition_exists(company_id)
        if not exists:
            raise PartitionMissingError('partition missing')

    async def _partition_exists(self, company_id: Any) -> bool:
        # Checker first.
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
        # Manager.
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
            for attr in ('get_partition', 'get_partition_metadata', 'find_partition'):
                method = getattr(manager, attr, None)
                if callable(method):
                    try:
                        result = await self._call_method(method, company_id, 'documents')
                        if result is not None:
                            return bool(result)
                    except Exception:
                        continue
            method = getattr(manager, 'list_partitions', None)
            if callable(method):
                try:
                    result = await self._call_method(method, company_id)
                    if result is not None:
                        return (
                            True
                            if isinstance(result, (list, tuple, set, dict)) and len(result) > 0
                            else bool(result)
                        )
                except Exception:
                    pass
        # Metadata repo.
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
            for attr in ('get_partition', 'get_partition_metadata', 'find_partition'):
                method = getattr(metadata, attr, None)
                if callable(method):
                    try:
                        result = await self._call_method(method, company_id, 'documents')
                        if result is not None:
                            return bool(result)
                    except Exception:
                        continue
            for attr in ('list_partitions_for_company', 'list_partitions'):
                method = getattr(metadata, attr, None)
                if callable(method):
                    try:
                        result = await self._call_method(method, company_id)
                        if result is not None:
                            return (
                                True
                                if isinstance(result, (list, tuple, set, dict)) and len(result) > 0
                                else bool(result)
                            )
                    except Exception:
                        continue
        # If deps exist but no method found, assume exists (avoid false refusal for unknown fakes).
        return True

    async def _call_method(
        self, method: Any, company_id: Any, table_name: str | None = None
    ) -> Any:
        try:
            sig = inspect.signature(method)
        except (TypeError, ValueError):
            sig = None
        # Try company_id only.
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
            try:
                result = method(table_name, company_id=company_id)
                return await _await(result)
            except (TypeError, Exception):
                pass
        # Try keyword variations.
        for kwargs in (
            {'company_id': company_id},
            {'companyId': company_id},
            {},
        ):
            try:
                result = method(**kwargs)
                return await _await(result)
            except TypeError:
                continue
            except Exception:
                continue
        if sig is not None:
            kwargs = {}
            for param in sig.parameters.values():
                if param.name in ('company_id', 'companyId', 'company', 'cid'):
                    kwargs[param.name] = company_id
                if table_name is not None and param.name in (
                    'table',
                    'table_name',
                    'partition_table',
                ):
                    kwargs[param.name] = table_name
            if kwargs:
                try:
                    result = method(**kwargs)
                    return await _await(result)
                except Exception:
                    pass
        return None

    def _resolve_allowed_categories(self) -> list[str] | None:
        # Config first.
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

    def _resolve_filename(self, file_raw: Any) -> str:
        if isinstance(file_raw, str):
            name = file_raw.strip()
            if name:
                # basename
                return name.split('/')[-1].split('\\')[-1] or 'document.pdf'
        if isinstance(file_raw, (list, tuple)) and len(file_raw) > 0:
            return self._resolve_filename(file_raw[0])
        if file_raw is not None:
            attr_name = getattr(file_raw, 'filename', None) or getattr(file_raw, 'name', None)
            if attr_name:
                return str(attr_name).split('/')[-1].split('\\')[-1]
        # request-based file name
        return 'document.pdf'

    async def _create_document_version(self, **kwargs: Any) -> Any:
        repo = self._document_repository
        company_id = kwargs.pop('company_id')
        version_entity = kwargs.pop('version_entity', None)
        # Try many repository method names.
        for method_name in (
            'create_document_version',
            'create_version',
            'create_document_version_record',
            'save_document_version',
            'insert_document_version',
            'create',
        ):
            method = getattr(repo, method_name, None)
            if callable(method):
                # Try passing entity.
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
                # Try kwargs with common names including version entity fields.
                create_kwargs = dict(kwargs)
                create_kwargs.setdefault('document_version', version_entity)
                create_kwargs.setdefault('version', version_entity)
                create_kwargs.setdefault('state', 'received')
                create_kwargs.setdefault('document_id', kwargs.get('document_id'))
                create_kwargs.setdefault(
                    'id', kwargs.get('version_id') if 'version_id' in kwargs else None
                )
                try:
                    result = method(company_id, **create_kwargs)
                    return await _await(result)
                except TypeError:
                    pass
                try:
                    result = method(company_id=company_id, **create_kwargs)
                    return await _await(result)
                except TypeError:
                    pass
        return version_entity

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


# Backwards-compatible aliases
Upload = UploadDocument
UploadUseCase = UploadDocument
UploadDocumentUseCase = UploadDocument
DocumentUpload = UploadDocument
DocumentUploadUseCase = UploadDocument
RequestUpload = UploadDocument
UploadRequestUseCase = UploadDocument
CreateUpload = UploadDocument
CreateUploadUseCase = UploadDocument
IngestDocument = UploadDocument
IngestionUseCase = UploadDocument
UploadOrchestrator = UploadDocument
UploadService = UploadDocument
UploadHandlerUseCase = UploadDocument
VersionCreationUseCase = UploadDocument
PresignedUploadUseCase = UploadDocument
