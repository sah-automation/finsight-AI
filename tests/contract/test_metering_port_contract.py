"""Contract tests for the MeteringPort."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from finsight.adapters.metering.dynamo_metering import DynamoMetering
from finsight.core.config.price_table import load_price_table

if TYPE_CHECKING:
    from finsight.domain.ports import MeteringPort

pytestmark = pytest.mark.contract

COMPANY = 'contract-company-a'
OTHER_COMPANY = 'contract-company-b'


class _RecordingTable:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self.items.append(kwargs['Item'])
        return {}


class _FailingTable:
    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError('metering backend unavailable')


@pytest.fixture
def table() -> _RecordingTable:
    return _RecordingTable()


@pytest.fixture
def metering(table: _RecordingTable) -> MeteringPort:
    return DynamoMetering(
        table=table,
        table_name=f'metering-contract-{id(table)}',
        price_table=load_price_table(),
    )


class TestMeteringPortContract:
    async def test_records_usage_for_the_calling_company(self, metering: MeteringPort) -> None:
        record = await metering.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=250,
            estimated_cost='0.05',
            trace_id='trace-1',
        )

        assert record is not None
        assert str(record.company_id) == COMPANY  # type: ignore[attr-defined]
        assert record.service == 'llm'  # type: ignore[attr-defined]
        assert record.model == 'openai/gpt-4o-mini'  # type: ignore[attr-defined]
        assert record.units == 250  # type: ignore[attr-defined]
        assert record.cost == Decimal('0.05')  # type: ignore[attr-defined]
        assert str(record.trace_id) == 'trace-1'  # type: ignore[attr-defined]

    async def test_repeat_writes_are_idempotent(self, metering: MeteringPort) -> None:
        for cost in ('0.05', '0.06'):
            await metering.record_usage(
                COMPANY,
                service='llm',
                model='openai/gpt-4o-mini',
                units=250,
                estimated_cost=cost,
                trace_id='trace-repeat',
            )

        records = metering.records()  # type: ignore[attr-defined]

        assert len(records) == 1

    async def test_rows_are_isolated_by_company(self, metering: MeteringPort) -> None:
        await metering.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=10,
            estimated_cost='0.01',
            trace_id='trace-shared',
        )
        await metering.record_usage(
            OTHER_COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=10,
            estimated_cost='0.01',
            trace_id='trace-shared',
        )

        records = metering.records()  # type: ignore[attr-defined]
        assert {record['pk'] for record in records} == {
            f'COMPANY#{COMPANY}',
            f'COMPANY#{OTHER_COMPANY}',
        }

    async def test_backend_failure_never_reaches_the_caller(self) -> None:
        metering = DynamoMetering(table=_FailingTable(), table_name='metering-contract-fail')

        result = await metering.record_usage(
            COMPANY,
            service='llm',
            model='openai/gpt-4o-mini',
            units=10,
            trace_id='trace-failure',
        )

        assert result is None
