"""Postgres/Neon KPI repository implementing the KpiRepository port.

Writes use ``INSERT ... ON CONFLICT`` on the ADR-0009 storage key and never
issue a DELETE. They do not commit, so ingestion can include them in its own
transaction. Reads go through the ``kpi_current`` view so selection, conflicts
and retention stay in one place. With no wired session the adapter uses an
in-memory seam for the contract suite.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.kpi_repository import KpiRepository as KpiRepositoryPort
from finsight.domain.ports.kpi_repository import KpiRow, KpiRows

from . import _kpi_repository_memory as _memory
from . import _kpi_repository_query as _query
from .base_repository import BaseRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import CompanyId

_FINGERPRINT_FIELDS = (
    'kpi_code',
    'period',
    'chart_period',
    'document_version_id',
    'computation_rule_version',
    'value',
    'computation_status',
    'source_citations',
    'source_metric_ids',
    'conflict_marker',
    'superseded_by_document_version_id',
)

_INSERT_COLUMNS = (
    'company_id',
    'kpi_code',
    'period',
    'document_version_id',
    'chart_period',
    'period_start',
    'chart_period_start',
    'currency',
    'units',
    'value',
    'computation_status',
    'estimation_method',
    'source_citations',
    'source_metric_ids',
    'computation_rule_version',
    'superseded_by_document_version_id',
)

_INSERT_SQL = """
INSERT INTO kpi_values (
    company_id, kpi_code, period, document_version_id, chart_period,
    period_start, chart_period_start, currency, units, value,
    computation_status, estimation_method, source_citations, source_metric_ids,
    computation_rule_version, superseded_by_document_version_id
) VALUES (
    :company_id, :kpi_code, :period, :document_version_id, :chart_period,
    :period_start, :chart_period_start, :currency, :units, :value,
    :computation_status, :estimation_method, CAST(:source_citations AS jsonb),
    CAST(:source_metric_ids AS jsonb),
    :computation_rule_version, :superseded_by_document_version_id
)
ON CONFLICT (company_id, kpi_code, period, document_version_id, chart_period)
DO UPDATE SET
    period_start = EXCLUDED.period_start,
    chart_period_start = EXCLUDED.chart_period_start,
    currency = EXCLUDED.currency,
    units = EXCLUDED.units,
    value = EXCLUDED.value,
    computation_status = EXCLUDED.computation_status,
    estimation_method = EXCLUDED.estimation_method,
    source_citations = EXCLUDED.source_citations,
    source_metric_ids = EXCLUDED.source_metric_ids,
    computation_rule_version = EXCLUDED.computation_rule_version,
    superseded_by_document_version_id = EXCLUDED.superseded_by_document_version_id,
    updated_at = now()
"""


def _row_params(row: Mapping[str, Any], company_id: str) -> dict[str, Any]:
    params = {column: row.get(column) for column in _INSERT_COLUMNS}
    params['company_id'] = company_id
    citations = row.get('source_citations') or []
    params['source_citations'] = json.dumps(list(citations))
    return params


def _as_mapping(row: Any) -> dict[str, Any]:
    mapping = getattr(row, '_mapping', row)
    return dict(mapping)


def _spec_value(spec: Any, field: str) -> Any:
    if isinstance(spec, Mapping):
        return spec.get(field)
    return getattr(spec, field, None)


class KpiRepository(KpiRepositoryPort, BaseRepository):
    """Tenant-scoped KPI store; SQL when wired, in-memory otherwise."""

    def __init__(self, config: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._memory: _memory.KpiMemory = {}

    async def upsert_batch(
        self,
        rows: Sequence[KpiRow],
        *,
        company_id: CompanyId | None = None,
        **kwargs: Any,
    ) -> int:
        prepared: list[dict[str, Any]] = []
        for row in rows:
            tenant = str(company_id or row.get('company_id') or '')
            if not tenant:
                raise ValueError('A KPI row requires company_id')
            if company_id is not None and str(row.get('company_id', tenant)) != str(company_id):
                raise ValueError('Cannot upsert a KPI row for another tenant')
            prepared.append(dict(row) | {'company_id': tenant})

        if self._session is None:
            written = 0
            for row in prepared:
                written += _memory.upsert_rows(self._memory, [row], str(row['company_id']))
            return written

        await self._write_prepared(prepared)
        return len(prepared)

    async def _set_tenant(self, tenant: str) -> None:
        await self._raw_execute(
            "SELECT set_config('app.company_id', :company_id, true)",
            {'company_id': tenant},
        )

    async def _clear_tenant(self) -> None:
        await self._raw_execute("SELECT set_config('app.company_id', CAST(NULL AS text), true)")
        self._rls_company_id = None

    async def _write_prepared(self, prepared: list[KpiRow]) -> None:
        # _raw_execute never commits: the caller owns the transaction so KPI
        # rows land with the source version, metrics and change events.
        for row in prepared:
            tenant = str(row['company_id'])
            await self._set_tenant(tenant)
            await self._raw_execute(_INSERT_SQL, _row_params(row, tenant))
        await self._clear_tenant()

    async def get_current(
        self,
        company_id: CompanyId,
        filters: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> KpiRows:
        values: dict[str, Any] = dict(kwargs)
        if filters:
            values = {**dict(filters), **values}
        tenant = str(company_id)

        if self._session is None:
            return _memory.apply_filters(_memory.current_rows(self._memory, tenant), values)

        sql, params = _query.build_select_sql({**values, 'company_id': tenant})
        await self._set_tenant(tenant)
        result = await self._raw_execute(sql, params)
        rows = [_as_mapping(row) for row in await self._fetchall(result)]
        await self._clear_tenant()
        return rows

    async def get_by_company_codes_periods(
        self,
        company_id: CompanyId,
        kpi_codes: Sequence[str],
        period_from: str | None = None,
        period_to: str | None = None,
        **kwargs: Any,
    ) -> KpiRows:
        filters = {
            'kpi_codes': list(kpi_codes),
            'period_from': period_from,
            'period_to': period_to,
            **kwargs,
        }
        return await self.get_current(company_id, filters)

    async def get_fingerprint_data(
        self,
        company_id: CompanyId,
        chart_specs: Sequence[Any],
        **kwargs: Any,
    ) -> dict[str, KpiRows]:
        result: dict[str, KpiRows] = {}
        for spec in chart_specs:
            chart_id = str(_spec_value(spec, 'chart_id'))
            codes = _spec_value(spec, 'kpi_codes') or []
            rows = await self.get_current(company_id, {'kpi_codes': list(codes), **kwargs})
            result[chart_id] = [
                {field: row.get(field) for field in _FINGERPRINT_FIELDS} for row in rows
            ]
        return result
