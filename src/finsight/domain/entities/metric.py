"""Metric entity - extracted finance figure."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from finsight.core.types import CompanyId, MetricId
from finsight.domain.value_objects.currency import Currency


def _now() -> datetime:
    return datetime.now(UTC)


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


class Metric:
    """A financial metric carrying value, unit, currency, period, document and
    source location."""

    def __init__(self, *args: object, **kwargs: object) -> None:  # noqa: PLR0912, PLR0915
        positional = [
            'metric_id',
            'company_id',
            'name',
            'value',
            'unit',
            'currency',
            'period',
            'document_id',
            'document',
            'source_location',
        ]
        data: dict[str, object] = dict.fromkeys(positional)
        for index, value in enumerate(args):
            if index < len(positional):
                data[positional[index]] = value

        def coalesce(*names: str, default: object = None) -> object:
            for name in names:
                if name in kwargs and kwargs[name] is not None:
                    return kwargs[name]
            for name in names:
                if data.get(name) is not None:
                    return data.get(name)
            return default

        ident = coalesce('metric_id', 'id', 'metricId', 'metricID', default=None)
        if ident is None:
            ident = str(__import__('uuid').uuid4())
        company_id = coalesce('company_id', 'companyId', 'tenant_id', default=None)
        name = coalesce('name', 'metric_name', 'metric', 'label', default=None)
        value = coalesce('value', 'amount', 'figure', 'metric_value', default=None)
        if value is None and 'value' not in kwargs and not args:
            # Allow partially constructed metrics only when value explicitly absent.
            pass
        unit = coalesce('unit', 'units', 'unit_of_measure', default=None)
        currency = coalesce('currency', default=None)
        period = coalesce('period', 'fiscal_period', 'reporting_period', default=None)
        document_id = coalesce(
            'document_id',
            'document',
            'doc_id',
            'documentId',
            'document_version',
            'document_version_id',
            'version_id',
            default=None,
        )
        source_location = coalesce(
            'source_location',
            'source',
            'location',
            'source_loc',
            default=None,
        )
        source_page = coalesce('source_page', 'page', 'page_number', default=None)
        source_table = coalesce('source_table', 'table', 'table_id', default=None)
        source_chunk_id = coalesce('source_chunk_id', 'chunk_id', 'chunk', default=None)
        start_char = coalesce('start_char', 'start', default=None)
        end_char = coalesce('end_char', 'end', default=None)
        version_id = coalesce('version_id', 'document_version', 'document_version_id', default=None)
        category = coalesce('category', default=None)
        created_at = coalesce('created_at', 'createdAt', default=None)
        updated_at = coalesce('updated_at', 'updatedAt', default=None)

        # Require a value to exist for a metric.
        if value is None:
            raise TypeError('Metric requires a value')

        if created_at is None:
            created_at = _now()
        if updated_at is None:
            updated_at = created_at

        if currency is not None and not isinstance(currency, Currency):
            with contextlib.suppress(ValueError):
                currency = Currency(str(currency))

        if source_location is None:
            location_data: dict[str, object] = {}
            if source_page is not None:
                location_data['page'] = source_page
            if source_table is not None:
                location_data['table'] = source_table
            if source_chunk_id is not None:
                location_data['chunk'] = source_chunk_id
            if start_char is not None:
                location_data.setdefault('start_char', start_char)
            if end_char is not None:
                location_data.setdefault('end_char', end_char)
            source_location = location_data or None

        self.metric_id = MetricId(str(ident))
        self.id = self.metric_id
        self.company_id = None if company_id is None else CompanyId(str(company_id))
        self.name = None if name is None else str(name)
        self.value = value
        self.unit = None if unit is None else str(unit)
        self.currency = currency
        self.period = period
        self.document_id = None if document_id is None else str(document_id)
        self.document = self.document_id
        self.document_version = version_id
        self.version_id = version_id
        self.source_location = source_location
        self.source = source_location
        self.location = source_location
        self.source_page = source_page
        self.source_table = source_table
        self.source_chunk_id = source_chunk_id
        self.source_chunk = source_chunk_id
        self.category = None if category is None else str(category)
        self.created_at = created_at
        self.updated_at = updated_at

    def __repr__(self) -> str:
        return f'Metric(metric_id={self.metric_id!r}, value={self.value!r})'


__all__ = ['Metric']
