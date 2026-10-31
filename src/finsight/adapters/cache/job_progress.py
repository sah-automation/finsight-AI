"""DynamoDB job progress (rebuildable view) adapter."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.job_progress_port import JobProgressPort

from ._job_progress_helpers import (
    _PROGRESS_STORES,
    _coerce_str,
    _config_value,
    _first,
    _is_table,
    _resolve_config,
)
from ._job_progress_operations import _JobProgressOperations


class JobProgress(_JobProgressOperations, JobProgressPort):
    """DynamoDB job progress (rebuildable view) adapter."""

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
