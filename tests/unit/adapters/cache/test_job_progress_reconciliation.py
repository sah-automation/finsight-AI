"""Adapter-level reconciliation tests for the DynamoDB job progress view."""

from __future__ import annotations

from typing import Any

import pytest

from finsight.adapters.cache.job_progress import JobProgress
from finsight.core.types import CompanyId

pytestmark = pytest.mark.unit

COMPANY = CompanyId('company-a')


class _ConditionalCheckFailedError(Exception):
    def __init__(self) -> None:
        super().__init__('conditional check failed')
        self.response = {'Error': {'Code': 'ConditionalCheckFailedException'}}


class _FakeTable:
    """Minimal DynamoDB table that honours the adapter's condition expressions."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}
        self.put_calls = 0
        self.after_read: Any = None

    @staticmethod
    def _key(item: dict[str, Any]) -> tuple[str, str]:
        return (str(item.get('job_id')), str(item.get('company_id')))

    def _lookup(self, key: dict[str, Any]) -> dict[str, Any] | None:
        if 'job_id' in key:
            return self.items.get((str(key['job_id']), str(key['company_id'])))
        for item in self.items.values():
            if item.get('pk') == key.get('pk'):
                return item
        return None

    async def get_item(self, **kwargs: Any) -> dict[str, Any]:
        item = self._lookup(kwargs['Key'])
        result = {'Item': dict(item)} if item is not None else {}
        hook = self.after_read
        if hook is not None:
            self.after_read = None
            hook(self)
        return result

    async def put_item(self, **kwargs: Any) -> None:
        self.put_calls += 1
        item = kwargs['Item']
        current = self.items.get(self._key(item))
        condition = kwargs.get('ConditionExpression')
        if condition is not None:
            attribute = kwargs['ExpressionAttributeNames']['#order']
            if condition == 'attribute_not_exists(#order)':
                if current is not None and attribute in current:
                    raise _ConditionalCheckFailedError
            else:
                expected = kwargs['ExpressionAttributeValues'][':expected']
                same_token = current is not None and attribute in current
                if same_token and current[attribute] != expected:
                    raise _ConditionalCheckFailedError
        self.items[self._key(item)] = dict(item)

    async def delete_item(self, **kwargs: Any) -> None:
        item = self._lookup(kwargs['Key'])
        if item is not None:
            self.items.pop(self._key(item), None)


def _progress(table: _FakeTable) -> JobProgress:
    return JobProgress(table=table, table_name=f'job-progress-{id(table)}')


async def test_stale_and_duplicate_reconciles_do_not_write() -> None:
    table = _FakeTable()
    progress = _progress(table)

    await progress.reconcile_progress(
        COMPANY, 'job-1', status='committed', progress=100, revision=3
    )
    writes_after_first = table.put_calls

    await progress.reconcile_progress(
        COMPANY, 'job-1', status='processing', progress=10, revision=2
    )
    await progress.reconcile_progress(COMPANY, 'job-1', status='failed', progress=0, revision=3)

    assert table.put_calls == writes_after_first
    stored = table.items[('job-1', str(COMPANY))]
    assert stored['status'] == 'committed'
    assert stored['progress'] == 100
    assert stored['revision'] == 3


async def test_concurrent_newer_write_wins_without_being_overwritten() -> None:
    table = _FakeTable()
    progress = _progress(table)
    await progress.reconcile_progress(
        COMPANY, 'job-race', status='committed', progress=100, revision=3
    )

    def concurrent_commit(target: _FakeTable) -> None:
        target.items[('job-race', str(COMPANY))] = {
            'job_id': 'job-race',
            'company_id': str(COMPANY),
            'status': 'committed',
            'progress': 100,
            'revision': 5,
        }

    table.after_read = concurrent_commit

    record = await progress.reconcile_progress(
        COMPANY, 'job-race', status='processing', progress=40, revision=4
    )

    assert record.get('revision') == 5
    stored = table.items[('job-race', str(COMPANY))]
    assert stored['revision'] == 5
    assert stored['status'] == 'committed'


async def test_table_is_authoritative_over_a_stale_process_cache() -> None:
    table = _FakeTable()
    progress = _progress(table)
    await progress.reconcile_progress(
        COMPANY, 'job-cache', status='committed', progress=100, revision=3
    )

    # Simulate another worker holding an older local mirror.
    progress._store_memory(
        {
            'job_id': 'job-cache',
            'company_id': str(COMPANY),
            'status': 'processing',
            'progress': 10,
            'revision': 1,
        }
    )

    await progress.reconcile_progress(
        COMPANY, 'job-cache', status='processing', progress=20, revision=2
    )

    stored = table.items[('job-cache', str(COMPANY))]
    assert stored['status'] == 'committed'
    assert stored['revision'] == 3
