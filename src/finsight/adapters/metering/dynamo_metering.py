"""DynamoDB metering adapter."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.metering_port import MeteringPort

from ._metering_helpers import *  # noqa: F403
from ._metering_operations import (
    _init_metering,
    _record_usage,
    _records,
)


class DynamoMetering(MeteringPort):
    """Idempotent usage rows in the shared metering table."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _init_metering(self, *args, **kwargs)

    async def record_usage(
        self,
        company_id: object,
        *,
        service: str | None = None,
        model: object = None,
        units: int = 1,
        unit_count: int | None = None,
        cost: object = None,
        estimated_cost: object = None,
        trace_id: object = None,
        trace: object = None,
        metadata: dict[str, object] | None = None,
        attributes: dict[str, object] | None = None,
        **kwargs: object,
    ) -> object:
        return await _record_usage(
            self,
            company_id,
            service=service,
            model=model,
            units=units,
            unit_count=unit_count,
            cost=cost,
            estimated_cost=estimated_cost,
            trace_id=trace_id,
            trace=trace,
            metadata=metadata,
            attributes=attributes,
            **kwargs,
        )

    def records(self, company_id: object = None) -> list[dict[str, Any]]:
        return _records(self, company_id)


# Naming variants used across the project/tests.
DynamoDBMetering = DynamoMetering
DynamoMeteringAdapter = DynamoMetering
MeteringAdapter = DynamoMetering

__all__ = [
    'DynamoDBMetering',
    'DynamoMetering',
    'DynamoMeteringAdapter',
    'MeteringAdapter',
]
