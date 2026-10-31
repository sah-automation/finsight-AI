# ruff: noqa: PLR0911, PLR0915
"""Metering usage record model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def _coalesce(
    kwargs: dict[str, object], data: dict[str, object], *names: str, default: object = None
) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    for name in names:
        if data.get(name) is not None:
            return data.get(name)
    return default


def _as_decimal(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, bool)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except Exception:  # noqa: BLE001
            return None
    return value


class UsageRecord:
    """Typed usage/cost record produced by metering."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__setattr__('_initialized', False)
        positional = [
            'company_id',
            'service',
            'model',
            'units',
            'cost',
            'trace_id',
            'metadata',
        ]
        data = dict.fromkeys(positional)
        for index, value in enumerate(args):
            if index < len(positional):
                data[positional[index]] = value

        company_id = _coalesce(
            kwargs, data, 'company_id', 'company', 'tenant_id', 'account_id', default=None
        )
        service = _coalesce(kwargs, data, 'service', 'service_name', 'operation', default=None)
        model = _coalesce(kwargs, data, 'model', 'model_name', 'model_id', default=None)
        unit_count = _coalesce(
            kwargs, data, 'units', 'unit_count', 'unit_counts', 'count', default=0
        )
        cost = _coalesce(kwargs, data, 'cost', 'estimated_cost', 'price', 'amount', default=None)
        trace_id = _coalesce(
            kwargs, data, 'trace_id', 'trace', 'trace_identifier', 'request_id', default=None
        )
        metadata = _coalesce(
            kwargs, data, 'metadata', 'attributes', 'tags', 'context', default=None
        )

        payload = kwargs.get('usage') or kwargs.get('row') or kwargs.get('record')
        if isinstance(payload, dict):
            company_id = (
                company_id
                if company_id is not None
                else payload.get('company_id') or payload.get('company')
            )
            service = service if service is not None else payload.get('service')
            model = (
                model
                if model is not None
                else payload.get('model') or payload.get('model_name') or payload.get('model_id')
            )
            if unit_count in (0, None):
                unit_count = payload.get('units', payload.get('unit_count', 0))
            cost = cost if cost is not None else payload.get('cost', payload.get('estimated_cost'))
            trace_id = (
                trace_id if trace_id is not None else payload.get('trace_id', payload.get('trace'))
            )
            metadata = (
                metadata
                if metadata is not None
                else payload.get('metadata', payload.get('attributes'))
            )

        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {'value': metadata}

        self.company_id = company_id
        self.company = company_id
        self.tenant_id = company_id
        self.service = None if service is None else str(service)
        self.model = model
        self.model_id = model
        self.model_name = model
        self.units = unit_count
        self.unit_count = unit_count
        self.count = unit_count
        self.cost = _as_decimal(cost)
        self.estimated_cost = self.cost
        self.price = self.cost
        self.trace_id = trace_id
        self.trace = trace_id
        self.trace_identifier = trace_id
        self.metadata = metadata
        self.attributes = metadata
        self.tags = metadata
        self.created_at = _coalesce(kwargs, data, 'created_at', 'timestamp', default=None)
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        self.record_id = _coalesce(kwargs, data, 'record_id', 'id', 'usage_id', default=None)
        if self.record_id is None:
            seed = f'{self.company_id}:{self.trace_id}:{self.service}:{self.model}'
            self.record_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))
        self.id = self.record_id
        super().__setattr__('_initialized', True)

    @property
    def idempotency_key(self) -> tuple[object, object, object, object]:
        return (self.company_id, self.trace_id, self.service, self.model)

    def to_dict(self) -> dict[str, object]:
        return {
            'company': self.company_id,
            'company_id': self.company_id,
            'service': self.service,
            'model': self.model,
            'units': self.units,
            'unit_count': self.unit_count,
            'cost': self.cost,
            'estimated_cost': self.estimated_cost,
            'trace_id': self.trace_id,
            'trace': self.trace_id,
            'metadata': self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f'UsageRecord(company={self.company_id!r}, service={self.service!r}, '
            f'model={self.model!r}, units={self.units!r})'
        )


MeteringRecord = UsageRecord
UsageEntry = UsageRecord
Usage = UsageRecord
MeteringUsage = UsageRecord
MeteringEvent = UsageRecord
UsageModel = UsageRecord
MeteringModel = UsageRecord

__all__ = [
    'MeteringEvent',
    'MeteringModel',
    'MeteringRecord',
    'MeteringUsage',
    'Usage',
    'UsageEntry',
    'UsageModel',
    'UsageRecord',
]
