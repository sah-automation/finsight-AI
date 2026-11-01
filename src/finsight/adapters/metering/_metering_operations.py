# ruff: noqa: PLC0415
"""Metering adapter operation helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from finsight.core.config.price_table import (
    PriceNotFoundError,
)
from finsight.domain.value_objects.usage_record import UsageRecord

from ._metering_helpers import (
    _DEFAULT_TABLE_NAME,
    _TABLES,
    _coerce_price_table,
    _config_value,
    _decimal_text,
    _first,
    _is_table,
    _maybe_await,
    _resolve_config,
    _resolve_switches_enabled,
    _text,
)

_LOGGER = logging.getLogger(__name__)


def _init_metering(self: Any, *args: Any, **kwargs: Any) -> None:
    self.config = _resolve_config(*args, **kwargs)
    config = self.config

    self.table_name = (
        _text(
            _first(kwargs, 'table_name', 'metering_table', 'name', default=None)
            or _config_value(config, 'table_name', default=_DEFAULT_TABLE_NAME)
        ).strip()
        or _DEFAULT_TABLE_NAME
    )

    self.price_table = _coerce_price_table(
        _first(kwargs, 'price_table', 'prices', default=None)
        or _config_value(config, 'price_table', default=None)
    )
    self.currency = getattr(self.price_table, 'currency', None) or _config_value(
        config, 'currency', default='USD'
    )

    raw_enabled = _first(kwargs, 'enabled', 'metering_enabled', default=None)
    self.enabled = _resolve_switches_enabled(config) if raw_enabled is None else bool(raw_enabled)
    self.metering_enabled = self.enabled

    self.table = None
    self.resource = None
    candidate = _first(
        kwargs,
        'table',
        'dynamodb_table',
        'resource',
        'dynamodb',
        'dynamodb_resource',
        'dynamodb_client',
        'client',
        default=None,
    )
    self.table_injected = candidate is not None
    if _is_table(candidate):
        self.table = candidate
    elif candidate is not None:
        _attach_resource(self, candidate)

    if self.table is None:
        try:
            import boto3  # type: ignore[import-untyped]

            resource = boto3.resource('dynamodb')
            self.table = resource.Table(self.table_name)
            self.resource = resource
        except Exception as exc:  # pragma: no cover
            _LOGGER.debug('metering dynamodb resource unavailable: %s', exc)
            self.table = None

    self._memory = _TABLES.setdefault(self.table_name, {})


def _attach_resource(self: Any, candidate: Any) -> None:
    try:
        if hasattr(candidate, 'Table'):
            self.resource = candidate
            self.table = candidate.Table(self.table_name)
        elif hasattr(candidate, 'resource'):
            self.resource = candidate.resource('dynamodb')
            self.table = self.resource.Table(self.table_name)
    except Exception as exc:
        _LOGGER.warning('metering table is unavailable: %s', exc)
        self.table = None


async def _record_usage(
    self: Any,
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
    """Record a single usage row, never raising to the caller."""
    if not self.enabled or not _text(company_id).strip():
        return None
    try:
        record = _build_record(
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
        item = _to_item(self, record)
    except Exception as exc:
        _LOGGER.warning(
            'metering write failed for company=%s trace=%s: %s',
            _text(company_id),
            _text(trace_id if trace_id is not None else trace),
            exc,
        )
        return None
    try:
        await _persist(self, item)
    except Exception as exc:
        _LOGGER.warning(
            'metering write failed for company=%s trace=%s: %s',
            _text(company_id),
            _text(trace_id if trace_id is not None else trace),
            exc,
        )
        if getattr(self, 'table_injected', False):
            return None
        # Auto-provisioned/unavailable backing stores fall back to the
        # in-memory mirror while still returning the recorded entry.
        return record
    return record


def _records(self: Any, company_id: object = None) -> list[dict[str, Any]]:
    company = None if company_id is None else _text(company_id)
    return [
        dict(item) for (pk, _sk), item in self._memory.items() if company is None or pk == company
    ]


def _build_record(
    self: Any,
    company_id: object,
    *,
    service: str | None,
    model: object,
    units: object,
    unit_count: object,
    cost: object,
    estimated_cost: object,
    trace_id: object,
    trace: object,
    metadata: dict[str, object] | None,
    attributes: dict[str, object] | None,
    **kwargs: object,
) -> UsageRecord:
    merged = _metadata(metadata, attributes, kwargs)
    payload = kwargs.get('usage') or kwargs.get('row') or kwargs.get('record')
    record = UsageRecord(
        company_id=company_id,
        service=service,
        model=model,
        units=unit_count if unit_count is not None else units,
        cost=cost if cost is not None else estimated_cost,
        trace_id=trace_id if trace_id is not None else trace,
        metadata=merged or None,
        usage=payload if isinstance(payload, Mapping) else None,
    )
    if record.cost is None and self.price_table is not None and record.model is not None:
        _apply_config_price(self, record)
    return record


def _metadata(
    metadata: dict[str, object] | None,
    attributes: dict[str, object] | None,
    kwargs: dict[str, object],
) -> dict[str, object]:
    merged: dict[str, object] = {}
    for source in (attributes, metadata):
        if isinstance(source, Mapping):
            merged.update(source)
    extra = kwargs.get('tags') or kwargs.get('context')
    if isinstance(extra, Mapping):
        merged.update(extra)
    return merged


def _apply_config_price(self: Any, record: Any) -> None:
    try:
        record.cost = self.price_table.cost_for(str(record.model), record.units or 0)
    except PriceNotFoundError as exc:
        _LOGGER.warning(
            'no configured price for model %s (units=%s): %s', record.model, record.units, exc
        )
        return
    record.estimated_cost = record.cost
    record.price = record.cost
    if record.estimated_cost is None:
        record.estimated_cost = record.cost


def _to_item(self: Any, record: Any) -> dict[str, Any]:
    metadata = (
        record.metadata if isinstance(record.metadata, Mapping) else {'value': record.metadata}
    )
    metadata_json = json.dumps(metadata, sort_keys=True, default=str)
    created_at = record.created_at
    if not isinstance(created_at, datetime):
        created_at = datetime.now(UTC)
    item: dict[str, Any] = {
        'pk': _text(record.company_id),
        'sk': str(record.record_id),
        'record_id': str(record.record_id),
        'company_id': _text(record.company_id),
        'currency': self.currency,
        'service': record.service,
        'model': _text(record.model),
        'model_name': _text(record.model),
        'units': _decimal_text(record.units),
        'unit_count': _decimal_text(record.unit_count),
        'cost': _decimal_text(record.cost),
        'estimated_cost': _decimal_text(record.estimated_cost),
        'price': _decimal_text(record.price),
        'trace_id': _text(record.trace_id),
        'created_at': created_at.isoformat(),
        'metadata': metadata_json,
    }
    return item


async def _persist(self: Any, item: dict[str, Any]) -> None:
    key = (item['pk'], item['sk'])
    self._memory[key] = dict(item)
    if self.table is None:
        return
    await _maybe_await(self.table.put_item, Item=item)
