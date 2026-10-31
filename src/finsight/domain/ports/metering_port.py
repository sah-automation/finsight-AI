# ruff: noqa: PLR0913
"""Port for recording usage/cost metering events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from finsight.domain.value_objects.usage_record import UsageRecord


class MeteringPort(ABC):
    """Interface for writing usage rows.

    Every paid call should emit one record through this port. Implementations
    must be idempotent by company, trace, service, and model.
    """

    @abstractmethod
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
        """Record one usage event."""
        _ = (
            company_id,
            service,
            model,
            units,
            unit_count,
            cost,
            estimated_cost,
            trace_id,
            trace,
            metadata,
            attributes,
            kwargs,
        )
        raise NotImplementedError

    async def record(
        self,
        company_id: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        return await self.record_usage(company_id, *args, **kwargs)  # type: ignore[arg-type]

    async def record_event(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def write_usage(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def write(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def track_usage(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def meter(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def meter_call(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def on_usage(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def put(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def emit(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def append(self, company_id: object, *args: Any, **kwargs: Any) -> Any:
        return await self.record_usage(company_id, *args, **kwargs)

    async def build_record(
        self,
        company_id: object,
        *args: object,
        **kwargs: object,
    ) -> UsageRecord:
        """Convenience factory used by adapters/tests."""
        return UsageRecord(company_id=company_id, **kwargs)

    def make_record(self, *args: Any, **kwargs: Any) -> UsageRecord:
        return UsageRecord(*args, **kwargs)


# Aliases.
Metering = MeteringPort
MeteringService = MeteringPort
UsageRecorder = MeteringPort
UsageMeter = MeteringPort
Meter = MeteringPort
MeteringGateway = MeteringPort
UsageTrackingPort = MeteringPort

__all__ = [
    'Meter',
    'Metering',
    'MeteringGateway',
    'MeteringPort',
    'MeteringService',
    'UsageMeter',
    'UsageRecorder',
    'UsageTrackingPort',
]
