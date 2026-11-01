"""Unit tests for the DynamoDB metering adapter."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from finsight.adapters.metering.dynamo_metering import DynamoMetering
from finsight.core.config.price_table import load_price_table

COMPANY = 'company-a'
OTHER_COMPANY = 'company-b'


class _FakeTable:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self.items.append(kwargs['Item'])
        return {}

    def unique_items(self) -> list[dict[str, Any]]:
        seen: dict[tuple[object, object], dict[str, Any]] = {}
        for item in self.items:
            seen[(item['pk'], item['sk'])] = item
        return list(seen.values())


class _FailingTable:
    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError('dynamodb unavailable')


@pytest.fixture
def table() -> _FakeTable:
    return _FakeTable()


@pytest.fixture
def adapter(table: _FakeTable) -> DynamoMetering:
    return DynamoMetering(
        table=table,
        table_name=f'metering-test-{id(table)}',
        price_table=load_price_table(),
    )


class TestDynamoMeteringWrites:
    async def test_numbers_are_string_encoded_decimals(
        self, adapter: DynamoMetering, table: _FakeTable
    ) -> None:
        await adapter.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=1500,
            estimated_cost='0.42',
            trace_id='trace-1',
        )

        item = table.items[0]
        assert isinstance(item['units'], str)
        assert Decimal(item['units']) == Decimal(1500)
        assert isinstance(item['cost'], str)
        assert Decimal(item['cost']) == Decimal('0.42')
        assert isinstance(item['estimated_cost'], str)
        assert Decimal(item['estimated_cost']) == Decimal('0.42')

    async def test_prices_are_resolved_from_configuration(
        self, adapter: DynamoMetering, table: _FakeTable
    ) -> None:
        await adapter.record_usage(
            COMPANY,
            service='llm',
            model='anthropic/claude-3-5-sonnet-20241022',
            units=1_000_000,
            trace_id='trace-price',
        )

        item = table.items[0]
        assert Decimal(item['cost']) == Decimal('3.00')

    async def test_metadata_is_stored_as_json(
        self, adapter: DynamoMetering, table: _FakeTable
    ) -> None:
        await adapter.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=10,
            trace_id='trace-meta',
            metadata={'cache_hit': True, 'retry': 2},
        )

        item = table.items[0]
        assert isinstance(item['metadata'], str)
        assert json.loads(item['metadata']) == {'cache_hit': True, 'retry': 2}

    async def test_writes_one_row_per_idempotency_key(
        self, adapter: DynamoMetering, table: _FakeTable
    ) -> None:
        for cost in ('0.10', '0.10'):
            await adapter.record_usage(
                COMPANY,
                service='llm',
                model='openai/gpt-4o-mini',
                units=100,
                estimated_cost=cost,
                trace_id='trace-idempotent',
            )

        assert len(table.unique_items()) == 1
        assert len(adapter.records()) == 1

    async def test_trace_model_service_and_company_are_part_of_the_key(
        self, adapter: DynamoMetering, table: _FakeTable
    ) -> None:
        common = {
            'service': 'llm',
            'model': 'openai/gpt-4o-mini',
            'units': 10,
            'estimated_cost': '0.01',
        }
        await adapter.record_usage(COMPANY, trace_id='trace-a', **common)
        await adapter.record_usage(COMPANY, trace_id='trace-b', **common)
        await adapter.record_usage(
            COMPANY, trace_id='trace-a', **{**common, 'model': 'openai/gpt-4o'}
        )
        await adapter.record_usage(
            COMPANY, trace_id='trace-a', **{**common, 'service': 'embedding'}
        )
        await adapter.record_usage(OTHER_COMPANY, trace_id='trace-a', **common)

        assert len(table.unique_items()) == 5
        assert {item['pk'] for item in table.items} == {
            f'COMPANY#{COMPANY}',
            f'COMPANY#{OTHER_COMPANY}',
        }


class TestDynamoMeteringFailureHandling:
    async def test_write_failure_does_not_raise(self) -> None:
        adapter = DynamoMetering(table=_FailingTable(), table_name='metering-test')

        result = await adapter.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=10,
            trace_id='trace-failure',
        )

        assert result is None

    async def test_disabled_metering_writes_nothing(self, table: _FakeTable) -> None:
        adapter = DynamoMetering(table=table, table_name='metering-test', enabled=False)

        result = await adapter.record_usage(COMPANY, service='llm', units=1, trace_id='trace-off')

        assert result is None
        assert table.items == []

    async def test_in_memory_fallback_when_no_table_is_injected(self) -> None:
        adapter = DynamoMetering(table_name='metering-memory-test')

        record = await adapter.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=10,
            estimated_cost='0.01',
            trace_id='trace-memory',
        )

        assert record is not None
        assert len(adapter.records()) == 1
