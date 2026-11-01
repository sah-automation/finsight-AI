"""Behavioral tests for metering adapter."""

from __future__ import annotations

import asyncio

from finsight.adapters.metering.dynamo_metering import DynamoMetering


def test_metering_records_usage_without_backing_table() -> None:
    metering = DynamoMetering()
    record = asyncio.run(metering.record_usage('co1', service='llm', model='m', trace_id='t'))
    assert getattr(record, 'company_id', None) == 'co1'
    assert len(metering.records('co1')) == 1


def test_metering_records_usage_with_injected_table() -> None:
    class _Table:
        async def put_item(self, **kwargs: object) -> None:
            return None

        async def get_item(self, key=None) -> dict[str, object]:
            return {'Item': None}

        async def batch_write_item(self, request_items=None) -> None:
            return None

    metering = DynamoMetering(table=_Table())
    record = asyncio.run(metering.record_usage('co1', service='llm', model='m', trace_id='t'))
    assert record is not None
    assert getattr(record, 'company_id', None) == 'co1'
