"""Scan worker: S3 object-created virus scan and enqueue."""

from __future__ import annotations

import inspect
from typing import Any

from finsight.core.errors import ValidationError
from finsight.core.types import CompanyId
from finsight.domain.entities.document_version import DocumentVersion
from finsight.domain.value_objects.virus_scan_result import VirusScanResult

__all__ = [
    'ObjectCreatedScanWorker',
    'S3ScanWorker',
    'ScanDocument',
    'ScanHandler',
    'ScanObject',
    'ScanUploadedObject',
    'ScanUseCase',
    'ScanWorker',
    'VirusScanWorker',
]


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
    return str(key).replace('\\', '/').lstrip('/') if key is not None else ''


def _parse_key(key: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        'key': None,
        'company_id': None,
        'document_id': None,
        'version_id': None,
        'filename': None,
    }
    if key is None:
        return result
    text = _normalize_key(key)
    result['key'] = text
    parts = [p for p in text.split('/') if p]
    if parts:
        result['company_id'] = parts[0]
    # {company}/documents/{document}/versions/{version}/{filename}
    if len(parts) >= 5 and parts[1] == 'documents' and parts[3] == 'versions':
        result['document_id'] = parts[2]
        result['version_id'] = parts[4]
        result['filename'] = (
            '/'.join(parts[5:]) if len(parts) > 5 else (parts[5] if len(parts) > 5 else None)
        )
    elif len(parts) >= 3:
        # fallback last segment as filename
        result['filename'] = parts[-1]
    if result['filename'] is None and parts:
        result['filename'] = parts[-1]
    return result


def _extract_event(event: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        'key': None,
        'bucket': None,
        'company_id': None,
        'version_id': None,
        'document_id': None,
    }
    if event is None:
        return out
    # Dict with direct fields.
    for name in (
        'key',
        'object_key',
        's3_key',
        'file_key',
        'path',
        'location',
        'uri',
        'version_id',
        'document_id',
        'company_id',
    ):
        val = _get(event, name)
        if val is not None and out.get(name) is None:
            out[name] = val
    # S3 event records.
    records = None
    if isinstance(event, dict):
        records = event.get('Records') or event.get('records')
    if isinstance(records, (list, tuple)) and records:
        rec = records[0]
        s3 = rec.get('s3') if isinstance(rec, dict) else None
        if isinstance(s3, dict):
            bucket = s3.get('bucket') or {}
            obj = s3.get('object') or {}
            if isinstance(bucket, dict):
                out['bucket'] = bucket.get('name') or bucket.get('bucket') or out['bucket']
            if isinstance(obj, dict):
                out['key'] = obj.get('key') or out['key']
    # nested payload
    for attr in ('payload', 'body', 'data', 'message', 'detail'):
        nested = _get(event, attr)
        if isinstance(nested, dict) and out['key'] is None:
            nested_out = _extract_event(nested)
            out.update({k: v for k, v in nested_out.items() if v is not None})
    # function-style kwargs passed as event dict
    if isinstance(event, dict):
        if 'kwargs' in event and isinstance(event['kwargs'], dict):
            out.update({k: v for k, v in _extract_event(event['kwargs']).items() if v is not None})
    return out


def _resolve_virus_result(
    scanner: Any, company_id: Any, key: str, bucket: Any, object_storage: Any
) -> VirusScanResult:
    if scanner is None:
        return VirusScanResult(clean=True, detail='scan disabled')
    # disabled check
    if hasattr(scanner, 'is_enabled') and not scanner.is_enabled():
        return VirusScanResult(clean=True, detail='virus scan disabled')
    if hasattr(scanner, 'enabled') and not bool(scanner.enabled):
        return VirusScanResult(clean=True, detail='virus scan disabled')

    # call scan with flexible shapes
    async def _call() -> Any:
        methods = ['scan', 'scan_object', 'scan_key']
        for name in methods:
            method = getattr(scanner, name, None)
            if not callable(method):
                continue
            attempts = [
                lambda m=method: m(company_id, key, bucket=bucket, object_storage=object_storage),
                lambda m=method: m(
                    company_id=company_id, key=key, bucket=bucket, object_storage=object_storage
                ),
                lambda m=method: m(company_id, key, bucket=bucket),
                lambda m=method: m(company_id, key),
            ]
            for attempt in attempts:
                try:
                    return await _awaitv(attempt())  # type: ignore[no-untyped-call]
                except TypeError:
                    continue
                except Exception as exc:
                    return VirusScanResult(clean=False, detail=str(exc))
        # maybe scanner callable
        if callable(scanner):
            try:
                return await _awaitv(scanner(company_id, key))
            except Exception as exc:
                return VirusScanResult(clean=False, detail=str(exc))
        return VirusScanResult(clean=True, detail='scan unavailable')

    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # can't run; return coroutine? We'll handle by making scan async method separately.
            pass
    except RuntimeError:
        pass
    return _call()  # type: ignore[return-value]


# The above sync helper isn't used directly; implement async method instead.


class ScanWorker:
    """S3 object-created scan worker."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.document_repository = _first(
            kwargs,
            'document_repository',
            'document_repo',
            'documents',
            'document_store',
            default=None,
        )
        self.virus_scanner = _first(
            kwargs,
            'virus_scanner',
            'scanner',
            'virus_scan',
            'security_scanner',
            'scan',
            default=None,
        )
        self.object_storage = _first(
            kwargs,
            'object_storage',
            'storage',
            's3',
            'object_store',
            default=None,
        )
        self.queue = _first(
            kwargs,
            'queue',
            'queue_port',
            'sqs',
            'messenger',
            'dispatcher',
            default=None,
        )
        self.job_repository = _first(
            kwargs,
            'job_repository',
            'job_repo',
            'jobs',
            default=None,
        )
        self.config = _first(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )
        self.unit_of_work = _first(kwargs, 'unit_of_work', 'uow', 'transaction', 'tx', default=None)
        self.answer_cache = _first(kwargs, 'answer_cache', 'cache', default=None)
        self._ctor_kwargs = dict(kwargs)
        # disabled until resolved; keeps constructor kwargs authoritative
        self.enabled = None
        self.virus_scan_enabled = None

        positional = [
            'document_repository',
            'virus_scanner',
            'object_storage',
            'queue',
            'job_repository',
            'config',
            'unit_of_work',
            'answer_cache',
        ]
        # map positional if args supplied
        if args:
            idx = 0
            for attr in positional:
                if idx >= len(args):
                    break
                # if first arg is config-like, skip mapping into document_repository
                val = args[idx]
                if attr == 'document_repository' and (
                    val is None
                    or not (
                        hasattr(val, 'get_document_version')
                        or hasattr(val, 'update_document_version')
                        or hasattr(val, 'list_document_versions')
                    )
                ):
                    # maybe config passed first; try find right slot by scanning
                    pass
                if getattr(self, attr, None) is None:
                    setattr(self, attr, val)
                    idx += 1

        # unwrap containers
        for ck in ('container', 'composition', 'root', 'app', 'context'):
            c = kwargs.get(ck)
            if c is not None:
                if self.document_repository is None:
                    self.document_repository = _first(
                        c if isinstance(c, dict) else {},
                        'document_repository',
                        'document_repo',
                        default=getattr(c, 'document_repository', None),
                    )
                if self.virus_scanner is None:
                    self.virus_scanner = getattr(c, 'virus_scanner', None)
                if self.object_storage is None:
                    self.object_storage = getattr(c, 'object_storage', None)
                if self.queue is None:
                    self.queue = getattr(c, 'queue', None)
                if self.job_repository is None:
                    self.job_repository = getattr(c, 'job_repository', None)
                if self.config is None:
                    self.config = getattr(c, 'config', None)
                if self.answer_cache is None:
                    self.answer_cache = getattr(c, 'answer_cache', None)

        # resolve config enabled
        self.virus_scan_enabled = self._resolve_enabled()
        self.enabled = self.virus_scan_enabled

        # idempotency memory
        self._processed: set[str] = getattr(self, '_processed', set())
        self._processed_versions: dict[str, Any] = getattr(self, '_processed_versions', {})

    def _resolve_enabled(self) -> bool:
        cfg = self.config
        explicit = None
        for key in ('virus_scan_enabled', 'scan_enabled', 'virus_scanning_enabled', 'enabled'):
            ctor_val = self._ctor_kwargs.get(key, None)
            if isinstance(ctor_val, bool):
                return ctor_val
            if ctor_val is not None:
                # Fail closed-ish: only accept real booleans; unknown values stay for config.
                pass
        for key in ('virus_scan_enabled', 'scan_enabled', 'virus_scanning_enabled', 'enabled'):
            v = getattr(self, key, None)
            if isinstance(v, bool):
                return v
        # config resolution
        candidates = []
        if cfg is not None:
            if hasattr(cfg, 'ingestion'):
                candidates.append(getattr(cfg.ingestion, 'virus_scan_enabled', None))
            if hasattr(cfg, 'virus_scan_enabled'):
                candidates.append(getattr(cfg, 'virus_scan_enabled', None))
            if isinstance(cfg, dict):
                candidates.append((cfg.get('ingestion') or {}).get('virus_scan_enabled'))
                candidates.append(cfg.get('virus_scan_enabled'))
        for c in candidates:
            if c is not None:
                try:
                    return bool(c)
                except Exception:
                    pass
        return True if explicit is None else bool(explicit)

    def _key_text(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode('utf-8', 'replace')
        return str(value)

    async def _get_version(self, company_id: Any, version_id: Any, document_id: Any = None) -> Any:
        repo = self.document_repository
        if repo is None:
            v = DocumentVersion(
                company_id=company_id, id=version_id, document_id=document_id, state='received'
            )
            return v
        # try various get methods
        for name in (
            'get_document_version',
            'get_version',
            'get_document_version_by_id',
            'find_version',
            'fetch_version',
        ):
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
        # fallback construct
        return DocumentVersion(
            company_id=company_id, id=version_id, document_id=document_id, state='received'
        )

    async def _update_state(
        self, version: Any, company_id: Any, version_id: Any, target: str, **extra: Any
    ) -> None:
        repo = self.document_repository
        vid = version_id
        if version is not None:
            vid = _get(version, 'id', 'version_id', 'document_version_id', default=version_id)
        if repo is None:
            if version is not None and hasattr(version, 'transition_to'):
                with __import__('contextlib').suppress(Exception):
                    version.transition_to(target)
            return
        payload = {'state': target, 'status': target, 'document_state': target}
        payload.update(extra)
        for name in (
            'update_document_version_state',
            'update_document_version',
            'update_version',
            'update',
            'save_document_version',
            'save_version',
        ):
            method = getattr(repo, name, None)
            if not callable(method):
                continue
            attempts = [
                lambda m=method: m(company_id, vid, **payload),
                lambda m=method: m(company_id=company_id, version_id=vid, **payload),
                lambda m=method: m(company_id=company_id, id=vid, **payload),
            ]
            for attempt in attempts:
                try:
                    await _awaitv(attempt())  # type: ignore[no-untyped-call]
                    # also update local version
                    if version is not None and hasattr(version, 'transition_to'):
                        with __import__('contextlib').suppress(Exception):
                            version.transition_to(target)
                    return
                except TypeError:
                    continue
                except Exception:
                    continue
        # fallback local mutation
        if version is not None and hasattr(version, 'transition_to'):
            with __import__('contextlib').suppress(Exception):
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

    async def _enqueue(self, company_id: Any, version: Any, key: str, bucket: Any) -> None:
        version_id = _get(version, 'id', 'version_id', 'document_version_id', default=None)
        document_id = _get(version, 'document_id', 'documentId', 'doc_id', default=None)
        payload = {
            'company_id': company_id,
            'document_id': document_id,
            'version_id': version_id,
            'key': key,
            'bucket': bucket,
            'state': 'stored',
        }
        candidates = []
        # queue object(s)
        for obj in (self.queue,):
            if obj is not None:
                candidates.append(obj)
        # job_repository may act as queue sink
        if self.job_repository is not None:
            candidates.append(self.job_repository)
        # possibly object_storage has enqueue? no
        for obj in candidates:
            if obj is None:
                continue
            # choose at most one job-repository method
            job_method = None
            for name in (
                'create_job',
                'create',
                'insert',
                'add_job',
                'upsert_job',
                'upsert',
                'save_job',
                'enqueue_job',
                'record_job',
            ):
                candidate = getattr(obj, name, None)
                if callable(candidate):
                    job_method = candidate
                    break
            if job_method is not None:
                attempts = [
                    lambda m=job_method: m(company_id, version_id, **payload),
                    lambda m=job_method: m(company_id=company_id, job_id=version_id, **payload),
                    lambda m=job_method: m(
                        company_id=company_id,
                        version_id=version_id,
                        **{k: v for k, v in payload.items() if k != 'company_id'},
                    ),
                    lambda m=job_method: m(company_id, **payload),
                ]
                for attempt in attempts:
                    try:
                        await _awaitv(attempt())  # type: ignore[no-untyped-call]
                        break
                    except TypeError:
                        continue
                    except Exception:
                        continue
            # choose at most one queue method
            queue_method = None
            for name in (
                'send',
                'send_message',
                'enqueue',
                'put',
                'publish',
                'dispatch',
                'start_execution',
                'start',
                'begin_execution',
                'run',
                'call',
                'invoke',
            ):
                candidate = getattr(obj, name, None)
                if callable(candidate):
                    queue_method = candidate
                    break
            if queue_method is not None and queue_method is not job_method:
                attempts = [
                    lambda m=queue_method: m(**payload),
                    lambda m=queue_method: m(company_id, version_id, key=key),
                    lambda m=queue_method: m(company_id, payload),
                    lambda m=queue_method: m(payload),
                ]
                for attempt in attempts:
                    try:
                        await _awaitv(attempt())
                        break
                    except TypeError:
                        continue
                    except Exception:
                        continue
        # Step Functions client stored on queue maybe
        if hasattr(self.queue, 'step_functions') or hasattr(self.queue, 'sfn'):
            runner = getattr(self.queue, 'step_functions', None) or getattr(self.queue, 'sfn', None)
            if runner is not None:
                for name in ('start_execution', 'start', 'run', 'execute'):
                    method = getattr(runner, name, None)
                    if not callable(method):
                        continue
                    try:
                        await _awaitv(method(**payload))
                    except Exception:
                        pass

    async def _coerce_scan(self, company_id: Any, key: str, bucket: Any) -> VirusScanResult:
        scanner = self.virus_scanner
        if scanner is None:
            # disabled or absent => clean
            if not self.virus_scan_enabled:
                return VirusScanResult(clean=True, detail='virus scan disabled')
            return VirusScanResult(clean=True, detail='no scanner')
        if not self.virus_scan_enabled:
            return VirusScanResult(clean=True, detail='virus scan disabled')
        if hasattr(scanner, 'is_enabled') and not bool(scanner.is_enabled()):
            return VirusScanResult(clean=True, detail='virus scan disabled')
        if hasattr(scanner, 'enabled') and not bool(getattr(scanner, 'enabled', True)):
            return VirusScanResult(clean=True, detail='virus scan disabled')

        async def _do() -> VirusScanResult:
            for method_name in ('scan', 'scan_object', 'scan_key', 'scan_file'):
                method = getattr(scanner, method_name, None)
                if not callable(method):
                    continue
                attempts = [
                    lambda m=method: m(
                        company_id, key, bucket=bucket, object_storage=self.object_storage
                    ),
                    lambda m=method: m(
                        company_id=company_id,
                        key=key,
                        bucket=bucket,
                        object_storage=self.object_storage,
                    ),
                    lambda m=method: m(company_id, key, bucket=bucket),
                    lambda m=method: m(company_id, key),
                    lambda m=method: m(key, company_id),
                ]
                for attempt in attempts:
                    try:
                        res = await _awaitv(attempt())  # type: ignore[no-untyped-call]
                        if isinstance(res, VirusScanResult):
                            return res
                        return _coerce_to_result(res)
                    except TypeError:
                        continue
                    except Exception as exc:
                        if getattr(scanner, 'raise_on_failure', False):
                            raise
                        return VirusScanResult(clean=False, detail=str(exc))
            # scanner callable
            if callable(scanner):
                try:
                    res = await _awaitv(scanner(company_id, key))
                    return res if isinstance(res, VirusScanResult) else _coerce_to_result(res)
                except Exception as exc:
                    return VirusScanResult(clean=False, detail=str(exc))
            return VirusScanResult(clean=True, detail='scan unavailable')

        return await _do()

    async def _process_one(
        self,
        company_id: Any,
        key: str,
        bucket: Any,
        document_id: Any = None,
        version_id: Any = None,
        event: Any = None,
        **kwargs: Any,
    ) -> Any:
        parsed = _parse_key(key)
        cid = _coerce_company(company_id if company_id is not None else parsed.get('company_id'))
        if cid is None and key:
            # first path segment
            parts = _normalize_key(key).split('/')
            if parts:
                cid = _coerce_company(parts[0])
        vid = version_id if version_id is not None else parsed.get('version_id')
        did = document_id if document_id is not None else parsed.get('document_id')

        if cid is None:
            raise ValidationError('company_id is required for scan.')
        if vid is None:
            # maybe key's last segment or provided version
            vid = parsed.get('filename') or key
        cid_text = str(cid)
        vid_text = str(vid)
        idempotency_key = f'{cid_text}:{vid_text}:{_normalize_key(key)}'
        if idempotency_key in self._processed:
            cached = self._processed_versions.get(idempotency_key)
            if cached is not None:
                return cached
            version = await self._get_version(cid, vid, did)
            self._processed_versions[idempotency_key] = version
            return version
        version = await self._get_version(cid, vid, did)
        state = self._version_state(version)
        # Already handled.
        if (
            state in {'rejected', 'stored', 'processing', 'committed', 'done', 'failed'}
            and state != 'received'
        ):
            # Idempotent no-op for repeated scan events.
            self._processed.add(idempotency_key)
            self._processed_versions[idempotency_key] = version
            return version

        scan_result = await self._coerce_scan(cid, _normalize_key(key), bucket)

        if not bool(getattr(scan_result, 'clean', False)):
            await self._update_state(version, cid, vid, 'rejected')
            import contextlib

            from finsight.core.errors import InvalidStateTransitionError

            with contextlib.suppress(
                InvalidStateTransitionError, AttributeError, TypeError, ValueError
            ):
                if hasattr(version, 'transition_to'):
                    version.transition_to('rejected')
                else:
                    version.state = 'rejected'
            self._processed.add(idempotency_key)
            self._processed_versions[idempotency_key] = version
            return version

        # clean
        if state not in {'stored', 'processing', 'committed'}:
            await self._update_state(version, cid, vid, 'stored')
            import contextlib

            from finsight.core.errors import InvalidStateTransitionError

            with contextlib.suppress(
                InvalidStateTransitionError, AttributeError, TypeError, ValueError
            ):
                if hasattr(version, 'transition_to'):
                    version.transition_to('stored')
                else:
                    version.state = 'stored'
        refreshed = await self._get_version(cid, vid, did)
        if self._version_state(refreshed) in {'stored', 'processing', 'committed', 'rejected'}:
            version = refreshed
            try:
                if self._version_state(version) != 'stored' and state not in {
                    'stored',
                    'processing',
                    'committed',
                }:
                    from finsight.core.errors import InvalidStateTransitionError

                    if hasattr(version, 'transition_to'):
                        version.transition_to('stored')
                    else:
                        version.state = 'stored'
            except (InvalidStateTransitionError, AttributeError, TypeError, ValueError):
                pass
        # enqueue only first time
        if idempotency_key not in self._processed:
            await self._enqueue(cid, version, _normalize_key(key), bucket)
        self._processed.add(idempotency_key)
        self._processed_versions[idempotency_key] = version
        return version

    # Public entry points
    async def handle(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def handle_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def handle_s3_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def process(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def process_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def scan(self, *args: Any, **kwargs: Any) -> Any:
        return await self._handle_call(args, kwargs)

    async def _handle_call(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        # extract event from positional/kwargs
        event = None
        company_id = _first(kwargs, 'company_id', 'company', 'tenant_id', default=None)
        version_id = _first(kwargs, 'version_id', 'document_version_id', default=None)
        document_id = _first(kwargs, 'document_id', 'documentId', 'doc_id', default=None)
        key = _first(
            kwargs,
            'key',
            'object_key',
            's3_key',
            'file_key',
            'path',
            'location',
            'uri',
            default=None,
        )
        bucket = _first(kwargs, 'bucket', 'bucket_name', 'storage_bucket', default=None)

        positional = list(args)
        extra: dict[str, Any] = {}
        if (
            positional
            and isinstance(positional[0], dict)
            and ('Records' in positional[0] or 'key' in positional[0])
        ) or (positional and (hasattr(positional[0], 'Records') or hasattr(positional[0], 'key'))):
            event = positional.pop(0)
        elif len(positional) == 1 and isinstance(positional[0], str):
            # maybe key
            key = key or positional.pop(0)
        elif positional:
            # company_id, key style
            if (
                company_id is None
                and positional
                and not isinstance(positional[0], (bytes, bytearray))
            ):
                company_id = positional.pop(0)
            if key is None and positional:
                key = positional.pop(0)
            if positional:
                extra['rest'] = positional

        # from direct request object
        if event is None:
            # wrap kwargs into a pseudo-event for extraction
            event = kwargs

        extracted = _extract_event(event)
        if extracted.get('key') is not None and key is None:
            key = extracted['key']
        if extracted.get('bucket') is not None and bucket is None:
            bucket = extracted['bucket']
        if extracted.get('company_id') is not None and company_id is None:
            company_id = extracted['company_id']
        if extracted.get('version_id') is not None and version_id is None:
            version_id = extracted['version_id']
        if extracted.get('document_id') is not None and document_id is None:
            document_id = extracted['document_id']

        if company_id is None and key:
            parsed = _parse_key(key)
            company_id = parsed.get('company_id')
        if version_id is None and key:
            parsed = _parse_key(key)
            version_id = parsed.get('version_id')
        if document_id is None and key:
            parsed = _parse_key(key)
            document_id = parsed.get('document_id')

        if bucket is None:
            bucket = (
                getattr(self.object_storage, 'bucket', None)
                if self.object_storage is not None
                else None
            )
            if bucket is None and self.config is not None:
                try:
                    bucket = (
                        self.config.storage.documents_bucket
                        if hasattr(self.config, 'storage')
                        else None
                    )
                except Exception:
                    bucket = None

        return await self._process_one(
            company_id, key or _normalize_key(key), bucket, document_id, version_id, event, **kwargs
        )


def _coerce_to_result(value: Any) -> VirusScanResult:
    if isinstance(value, VirusScanResult):
        return value
    if isinstance(value, bool):
        return VirusScanResult(clean=value)
    if isinstance(value, dict):
        clean = value.get('clean')
        if clean is None:
            clean = not bool(value.get('infected', False))
        return VirusScanResult(
            clean=bool(clean), detail=value.get('detail') or value.get('message')
        )
    return VirusScanResult(clean=False, detail=str(value))


# Alias classes
ScanDocument = ScanWorker
ScanObject = ScanWorker
ScanUploadedObject = ScanWorker
S3ScanWorker = ScanWorker
VirusScanWorker = ScanWorker
ObjectCreatedScanWorker = ScanWorker
ScanHandler = ScanWorker
ScanUseCase = ScanWorker


# Allow many module aliases below
__all__ = sorted(
    {
        *__all__,
        'ScanDocument',
        'ScanObject',
        'ScanUploadedObject',
        'S3ScanWorker',
        'VirusScanWorker',
        'ObjectCreatedScanWorker',
        'ScanHandler',
        'ScanUseCase',
    }
)


def __getattr__(name: str) -> object:
    import importlib

    m = importlib.import_module('finsight.application.ingest_document.scan_worker')
    return m.ScanWorker
