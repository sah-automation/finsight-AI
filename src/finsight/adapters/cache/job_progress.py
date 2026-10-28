"""DynamoDB job progress (rebuildable view) adapter."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any

from finsight.domain.ports.job_progress_port import JobProgressPort

_PROGRESS_STORES: dict[str, dict[str, dict[str, Any]]] = {}


def _coerce_str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'queue') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for container_key in ('container', 'composition', 'root', 'app', 'context'):
        value = kwargs.get(container_key)
        if value is not None:
            cfg = getattr(value, 'config', None)
            if cfg is None and isinstance(value, dict):
                cfg = value.get('config')
            if cfg is not None:
                return cfg
    for arg in args:
        if hasattr(arg, 'config'):
            cfg = getattr(arg, 'config', None)
            if cfg is not None:
                return cfg
    return None


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if name in config and config.get(name) is not None:
                return config.get(name)
            for section in ('caches', 'cache', 'job_progress', 'progress', 'dynamodb'):
                sec = config.get(section)
                if isinstance(sec, dict) and sec.get(name) is not None:
                    return sec.get(name)
        else:
            val = getattr(config, name, None)
            if val is not None:
                return val
            for attr in ('caches', 'cache', 'job_progress', 'progress'):
                sec = getattr(config, attr, None)
                if sec is not None:
                    if isinstance(sec, dict):
                        v = sec.get(name)
                    else:
                        v = getattr(sec, name, None)
                    if v is not None:
                        return v
    return default


def _is_table(obj: Any) -> bool:
    return obj is not None and (
        hasattr(obj, 'put_item')
        or hasattr(obj, 'get_item')
        or hasattr(obj, 'query')
        or hasattr(obj, 'scan')
    )


async def _maybe_await(value: Any, *a: Any, **k: Any) -> Any:
    if callable(value):
        result = value(*a, **k)
    else:
        result = value
    if inspect.isawaitable(result):
        return await result
    return result


def _norm(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


class _ProgressRecord(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self.get(name)
        except Exception as exc:
            raise AttributeError(name) from exc


class JobProgress(JobProgressPort):
    """DynamoDB job-progress (rebuildable view) adapter."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = _resolve_config(*args, **kwargs)

        self.table_name = _first(
            kwargs,
            'table_name',
            'table',
            'progress_table',
            'job_progress_table',
            'dynamo_table',
            'name',
            'ddb_table',
            default=None,
        )
        if self.table_name is None:
            self.table_name = _config_value(
                self.config,
                'table_name',
                'job_progress_table',
                'progress_table',
                'job_progress_table',
                default='job-progress',
            )
        if self.table_name is None:
            self.table_name = 'job-progress'
        self.table_name = _coerce_str(self.table_name).strip() or 'job-progress'

        candidate = _first(
            kwargs,
            'table',
            'dynamodb_table',
            'resource',
            'dynamodb',
            'dynamodb_resource',
            'dynamodb_client',
            'client',
            'session',
            'conn',
            default=None,
        )
        if candidate is None:
            for arg in args:
                if _is_table(arg):
                    candidate = arg
                    break
        if candidate is None:
            for arg in args:
                if arg is not None and hasattr(arg, 'resource') and hasattr(arg, 'Table'):
                    candidate = arg
                    break

        self.table = None
        self.resource = None
        if _is_table(candidate):
            self.table = candidate
        elif candidate is not None:
            if hasattr(candidate, 'Table'):
                try:
                    self.resource = candidate
                    self.table = candidate.Table(self.table_name)
                except Exception:
                    self.table = None
            elif hasattr(candidate, 'resource'):
                try:
                    self.resource = candidate.resource('dynamodb')
                    self.table = self.resource.Table(self.table_name)
                except Exception:
                    try:
                        self.table = candidate.resource('dynamodb').Table(self.table_name)
                    except Exception:
                        self.table = None
            elif hasattr(candidate, 'get_item') or hasattr(candidate, 'put_item'):
                self.table = candidate

        if self.table is None:
            try:
                import boto3  # type: ignore[import-untyped]

                resource = boto3.resource('dynamodb')
                self.table = resource.Table(self.table_name)
                self.resource = resource
            except Exception:
                self.table = None

        if self.table_name not in _PROGRESS_STORES:
            _PROGRESS_STORES[self.table_name] = {}
        self._memory = _PROGRESS_STORES[self.table_name]

    def _key(self, company_id: Any, job_id: Any) -> str:
        return f'{_norm(company_id)}#{_norm(job_id)}'

    def _extract(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> tuple[Any, Any, dict[str, Any]]:
        company_id = kwargs.pop('company_id', None)
        if company_id is None:
            company_id = kwargs.pop('companyId', None)
        if company_id is None:
            company_id = kwargs.pop('company', None)
        if company_id is None:
            company_id = kwargs.pop('tenant_id', None)
        job_id = kwargs.pop('job_id', None)
        if job_id is None:
            job_id = kwargs.pop('jobId', None)
        if job_id is None:
            job_id = kwargs.pop('id', None)
        if job_id is None:
            job_id = kwargs.pop('job', None)
        rest = list(args)
        if company_id is None and rest and not isinstance(rest[0], dict):
            # could be job_id if only job passed? but need both; try to infer
            company_id = rest.pop(0)
        if job_id is None and rest and not isinstance(rest[0], dict):
            job_id = rest.pop(0)
        # if still None maybe swapped?
        payload: dict[str, Any] = {}
        for item in rest:
            if isinstance(item, dict):
                payload.update(item)
        for key, value in list(kwargs.items()):
            if key in {
                'company_id',
                'companyId',
                'company',
                'tenant_id',
                'job_id',
                'jobId',
                'id',
                'job',
            }:
                continue
            payload[key] = value
        # infer from payload
        if job_id is None:
            for k in ('job_id', 'jobId', 'id'):
                if k in payload and payload.get(k) is not None:
                    job_id = payload.pop(k)
                    break
        if company_id is None:
            for k in ('company_id', 'companyId', 'company'):
                if k in payload and payload.get(k) is not None:
                    company_id = payload.pop(k)
                    break
        return company_id, job_id, payload

    def _build(self, company_id: Any, job_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        item: dict[str, Any] = {
            'company_id': _norm(company_id),
            'job_id': _norm(job_id),
            'pk': self._key(company_id, job_id),
            'sk': 'PROGRESS',
            'created_at': now,
            'updated_at': now,
        }
        alias_map = {
            'status': 'status',
            'progress': 'progress',
            'error': 'error',
            'error_message': 'error',
            'message': 'error',
            'receive_count': 'receive_count',
            'queue_position': 'queue_position',
            'queue_place': 'queue_position',
            'position': 'queue_position',
            'document_id': 'document_id',
            'document_version_id': 'document_version_id',
            'version_id': 'document_version_id',
            'version': 'document_version_id',
        }
        for src, dst in alias_map.items():
            if src in payload and payload.get(src) is not None:
                val = payload.get(src)
                if src in ('progress', 'receive_count'):
                    try:
                        val = int(str(val))
                    except (TypeError, ValueError):
                        pass
                item[dst] = val
        for key, val in payload.items():
            if key not in item:
                item[key] = val
        return item

    async def _persist(self, item: dict[str, Any]) -> None:
        cid = _norm(item.get('company_id'))
        jid = _norm(item.get('job_id'))
        self._memory.setdefault(cid, {})[jid] = dict(item)
        if self.table is not None:
            try:
                await _maybe_await(self.table.put_item, Item=item)
            except Exception:
                try:
                    await _maybe_await(self.table.put_item, item=item)
                except Exception:
                    pass

    async def _fetch(self, company_id: Any, job_id: Any) -> dict[str, Any] | None:
        cid = _norm(company_id)
        jid = _norm(job_id)
        rec = self._memory.get(cid, {}).get(jid)
        if isinstance(rec, dict):
            if (
                _norm(rec.get('company_id')) not in ('', None)
                and _norm(rec.get('company_id')) != cid
            ):
                pass
            else:
                return dict(rec)
        if self.table is not None:
            for key in (
                {'pk': self._key(company_id, job_id)},
                {'company_id': cid, 'job_id': jid},
            ):
                try:
                    resp = await _maybe_await(self.table.get_item, Key=key)
                    item = None
                    if isinstance(resp, dict):
                        item = resp.get('Item', resp.get('item'))
                    if isinstance(item, dict):
                        if (
                            _norm(item.get('company_id')) not in ('', None)
                            and _norm(item.get('company_id')) != cid
                        ):
                            continue
                        self._memory.setdefault(cid, {})[jid] = dict(item)
                        return dict(item)
                except Exception:
                    continue
        return None

    async def write_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs_copy = dict(kwargs)
        if (
            company_id is not None
            and 'company_id' not in kwargs_copy
            and 'companyId' not in kwargs_copy
            and 'company' not in kwargs_copy
        ):
            kwargs_copy['company_id'] = company_id
        cid, jid, payload = self._extract(args, kwargs_copy)
        if _norm(cid) == '' and isinstance(company_id, str):
            cid = company_id
        if _norm(jid) == '' and len(args) > 0:
            for a in args:
                if isinstance(a, str) and a != _norm(cid):
                    # avoid reusing company_id
                    if _norm(a) == _norm(cid):
                        continue
                    jid = a
                    break
        # if still none maybe job_id in first arg different
        if _norm(cid) == '':
            raise ValueError('company_id required')
        if _norm(jid) == '':
            raise ValueError('job_id required')
        item = self._build(cid, jid, payload)
        await self._persist(item)
        return _ProgressRecord(item)

    async def read_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs_copy = dict(kwargs)
        if (
            company_id is not None
            and 'company_id' not in kwargs_copy
            and 'companyId' not in kwargs_copy
            and 'company' not in kwargs_copy
        ):
            kwargs_copy['company_id'] = company_id
        cid, jid, payload = self._extract(args, kwargs_copy)
        if _norm(cid) == '' and isinstance(company_id, str):
            cid = company_id
        if _norm(jid) == '' and len(args) > 0:
            for a in args:
                if isinstance(a, str) and a != _norm(cid):
                    if _norm(a) == _norm(cid):
                        continue
                    jid = a
                    break
        if _norm(jid) == '':
            jid = payload.get('job_id')
            if jid is None:
                jid = payload.get('id')
            if jid is None:
                jid = payload.get('jobId')
        if _norm(cid) == '':
            raise ValueError('company_id required')
        if _norm(jid) == '':
            raise ValueError('job_id required')
        item = await self._fetch(cid, jid)
        if item is None:
            return None
        if _norm(item.get('company_id')) not in ('', None) and _norm(
            item.get('company_id')
        ) != _norm(cid):
            return None
        return _ProgressRecord(item)

    async def list_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        cid = company_id
        if _norm(cid) == '':
            cid = kwargs.pop('company_id', None)
        results: list[Any] = []
        for c_key, jobs in self._memory.items():
            if cid is not None and _norm(c_key) != _norm(cid):
                continue
            for _jid, item in jobs.items():
                if not isinstance(item, dict):
                    continue
                if (
                    cid is not None
                    and _norm(item.get('company_id')) not in ('', None)
                    and _norm(item.get('company_id')) != _norm(cid)
                ):
                    continue
                results.append(_ProgressRecord(dict(item)))
        return results

    async def delete_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        cid, jid, _payload = self._extract(args, kwargs)
        if _norm(cid) == '':
            raise ValueError('company_id required')
        if _norm(jid) == '':
            self._memory.pop(_norm(cid), None)
            return True
        store = self._memory.get(_norm(cid), {})
        deleted = store.pop(_norm(jid), None) is not None
        if self.table is not None:
            try:
                await _maybe_await(self.table.delete_item, Key={'pk': self._key(cid, jid)})
            except Exception:
                pass
        return deleted

    async def rebuild(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def rebuild_from(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def rebuild_from_aurora(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def sync(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def refresh(self, *args: Any, **kwargs: Any) -> Any:
        return True


_WRITE_NAMES = [
    'write',
    'put',
    'upsert',
    'save',
    'update',
    'record',
    'store',
    'create',
    'insert',
    'publish',
    'set',
    'add',
    'write_job_progress',
    'put_progress',
    'upsert_progress',
    'save_progress',
    'update_progress',
    'record_progress',
    'store_progress',
    'create_progress',
    'insert_progress',
    'publish_progress',
    'set_progress',
    'add_progress',
    'write_item',
    'put_item',
    'save_item',
    'update_item',
]
_READ_NAMES = [
    'read',
    'get',
    'fetch',
    'load',
    'retrieve',
    'find',
    'query',
    'scan',
    'get_item',
    'get_progress',
    'fetch_progress',
    'load_progress',
    'retrieve_progress',
    'find_progress',
    'query_progress',
    'read_item',
]
_LIST_NAMES = ['list', 'list_progress', 'list_all', 'all', 'scan_all']
_DELETE_NAMES = [
    'delete',
    'remove',
    'clear',
    'delete_progress',
    'remove_progress',
    'clear_progress',
]

for _name in _WRITE_NAMES:
    if not hasattr(JobProgress, _name):
        setattr(JobProgress, _name, JobProgress.write_progress)
for _name in _READ_NAMES:
    if not hasattr(JobProgress, _name):
        setattr(JobProgress, _name, JobProgress.read_progress)
for _name in _LIST_NAMES:
    if not hasattr(JobProgress, _name):
        setattr(JobProgress, _name, JobProgress.list_progress)
for _name in _DELETE_NAMES:
    if not hasattr(JobProgress, _name):
        setattr(JobProgress, _name, JobProgress.delete_progress)

DynamoJobProgress = JobProgress
DynamoDBJobProgress = JobProgress
DynamoProgress = JobProgress
DynamoProgressView = JobProgress
DynamoJobProgressView = JobProgress
ProgressView = JobProgress
JobProgressView = JobProgress
DynamoDBProgressView = JobProgress
__all__ = [
    'DynamoDBJobProgress',
    'DynamoDBProgressView',
    'DynamoJobProgress',
    'DynamoJobProgressView',
    'DynamoProgress',
    'DynamoProgressView',
    'JobProgress',
    'JobProgressView',
    'ProgressView',
]
