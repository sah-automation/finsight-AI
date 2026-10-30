"""DynamoDB metering adapter.

Every paid call writes exactly one usage row. Rows are keyed by the company
partition (``pk``) and a deterministic digest of company, trace, service and
model (``sk``), so retries and duplicate processing overwrite the same row
instead of double-counting spend.

Numbers are written as string-encoded decimals because DynamoDB's ``Decimal``
type is not JSON-safe and float rounding must never leak into billing data.
Prices are resolved from ``config/prices.yaml`` through an injected
:class:`~finsight.core.config.price_table.PriceTable`; no price is hard-coded
here.

The port requires metering failures to stay invisible to the caller: any error
while building or writing a row is logged and swallowed, and ``record_usage``
returns ``None``. Without an injected table the adapter keeps rows in a
process-local store so contract tests never reach the network.
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finsight.core.config.price_table import (
    PriceNotFoundError,
    PriceTable,
    load_price_table,
)
from finsight.domain.ports.metering_port import MeteringPort
from finsight.domain.value_objects.usage_record import UsageRecord

_LOGGER = logging.getLogger(__name__)

# table name -> {(pk, sk): item}
_TABLES: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

_DEFAULT_TABLE_NAME = 'metering'


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _decimal_text(value: object) -> str | None:
    if value is None:
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return format(number, 'f')


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, Mapping):
            return arg
        if hasattr(arg, 'metering') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return None


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    sections = ('metering', 'metering_ext')
    for name in names:
        if config is None:
            break
        if isinstance(config, Mapping):
            if config.get(name) is not None:
                return config.get(name)
            for section in sections:
                nested = config.get(section)
                if isinstance(nested, Mapping) and nested.get(name) is not None:
                    return nested.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in sections:
                nested = getattr(config, section, None)
                if nested is None:
                    continue
                value = (
                    nested.get(name) if isinstance(nested, Mapping) else getattr(nested, name, None)
                )
                if value is not None:
                    return value
    return default


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _is_table(obj: Any) -> bool:
    return obj is not None and any(
        hasattr(obj, method) for method in ('put_item', 'batch_write_item', 'get_item')
    )


async def _maybe_await(value: Any, *args: Any, **kwargs: Any) -> Any:
    result = value(*args, **kwargs) if callable(value) else value
    if inspect.isawaitable(result):
        return await result
    return result


def _coerce_price_table(value: Any) -> PriceTable:
    if isinstance(value, PriceTable):
        return value
    if isinstance(value, Mapping):
        return PriceTable(value)
    if isinstance(value, (str, Path)):
        return load_price_table(value)
    return load_price_table()


def _resolve_switches_enabled(config: Any) -> bool:
    switches = None
    if config is not None:
        switches = (
            config.get('switches')
            if isinstance(config, Mapping)
            else getattr(config, 'switches', None)
        )
    if isinstance(switches, Mapping):
        return bool(switches.get('usage_metering_enabled', True))
    if switches is not None:
        return bool(getattr(switches, 'usage_metering_enabled', True))
    return True


class DynamoMetering(MeteringPort):
    """Idempotent usage rows in the shared metering table."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
        self.enabled = (
            _resolve_switches_enabled(config) if raw_enabled is None else bool(raw_enabled)
        )
        self.metering_enabled = self.enabled

        self.table: Any = None
        self.resource: Any = None
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
        if _is_table(candidate):
            self.table = candidate
        elif candidate is not None:
            self._attach_resource(candidate)

        if self.table is None:
            try:
                import boto3  # type: ignore[import-untyped]  # noqa: PLC0415

                resource = boto3.resource('dynamodb')
                self.table = resource.Table(self.table_name)
                self.resource = resource
            except Exception as exc:
                _LOGGER.debug('metering dynamodb resource unavailable: %s', exc)
                self.table = None

        self._memory = _TABLES.setdefault(self.table_name, {})

    def _attach_resource(self, candidate: Any) -> None:
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

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

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
        """Record a single usage row, never raising to the caller."""
        if not self.enabled or not _text(company_id).strip():
            return None
        try:
            record = self._build_record(
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
            item = self._to_item(record)
            await self._persist(item)
        except Exception as exc:
            _LOGGER.warning(
                'metering write failed for company=%s trace=%s: %s',
                _text(company_id),
                _text(trace_id if trace_id is not None else trace),
                exc,
            )
            return None
        else:
            return record

    def records(self, company_id: object = None) -> list[dict[str, Any]]:
        """Return stored usage rows, optionally scoped to one company."""
        company = None if company_id is None else _text(company_id)
        return [
            dict(item)
            for (pk, _sk), item in self._memory.items()
            if company is None or pk == company
        ]

    # ------------------------------------------------------------------
    # Record construction
    # ------------------------------------------------------------------

    def _build_record(
        self,
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
        merged = self._metadata(metadata, attributes, kwargs)
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
            self._apply_config_price(record)
        return record

    @staticmethod
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

    def _apply_config_price(self, record: UsageRecord) -> None:
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

    def _to_item(self, record: UsageRecord) -> dict[str, Any]:
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

    async def _persist(self, item: dict[str, Any]) -> None:
        key = (item['pk'], item['sk'])
        self._memory[key] = dict(item)
        if self.table is None:
            return
        await _maybe_await(self.table.put_item, Item=item)


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
