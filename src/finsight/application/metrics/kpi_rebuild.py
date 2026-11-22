"""Rolling, idempotent KPI rebuild job (issue #377).

A change to the KPI definitions, computation rule, estimation methods or
``computation_rule_version`` produces a new target version. Its rebuild state
moves ``pending`` -> ``running`` -> ``complete``; the version is not active
until completion. Companies are rebuilt in configured batches through the
existing waiting line, and rows are only upserted on the ADR-0009 storage key:
no DELETE, so retrying a failed company is safe and history stays intact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from finsight.core.work_priority import assert_rebuild_priority_ordering

_ALLOWED_PRIORITIES = ('rebuilds', 'background')
_FINGERPRINT_FIELDS = (
    'codes',
    'budget_vs_actual_match',
    'estimation_methods',
    'tolerances',
)


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _config_section(config: Any) -> Any:
    return _attr(config, 'kpi', None) or config


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    dumper = getattr(value, 'model_dump', None)
    if callable(dumper):
        return _plain(dumper())
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _target_version(config: Any, explicit: str | None) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    section = _config_section(config)
    version = _attr(section, 'computation_rule_version', None) or _attr(
        config, 'computation_rule_version', None
    )
    if version is not None and str(version).strip():
        return str(version).strip()
    rules = {name: _plain(_attr(section, name)) for name in _FINGERPRINT_FIELDS}
    digest = hashlib.sha256(
        json.dumps(rules, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()[:12]
    return f'kpi-rules-{digest}'


def _company_id(value: Any) -> str:
    if isinstance(value, Mapping):
        value = _attr(value, 'company_id', None) or _attr(value, 'id', None)
    else:
        value = _attr(value, 'company_id', None) or _attr(value, 'id', None) or value
    return str(value).strip()


class KpiRebuildJob:
    """Rebuild KPI rows for every company at one target rule version."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        config: Any,
        metric_repository: Any,
        kpi_repository: Any,
        computation_service: Any,
        rebuild_state: Any,
        waiting_line: Any = None,
        company_repository: Any = None,
        target_version: str | None = None,
    ) -> None:
        section = _config_section(config)
        priority = str(_attr(section, 'rebuild_priority', 'rebuilds'))
        if priority not in _ALLOWED_PRIORITIES:
            raise ValueError(
                f'kpi.rebuild_priority must be one of {_ALLOWED_PRIORITIES}, got {priority!r}'
            )
        try:
            batch_size = int(_attr(section, 'rebuild_batch_size', 10))
        except (TypeError, ValueError) as exc:
            raise ValueError('kpi.rebuild_batch_size must be a positive integer') from exc
        if batch_size < 1:
            raise ValueError('kpi.rebuild_batch_size must be a positive integer')
        assert_rebuild_priority_ordering()

        self._priority = priority
        self._batch_size = batch_size
        self._version = _target_version(config, target_version)
        self._metric_repository = metric_repository
        self._kpi_repository = kpi_repository
        self._computation_service = computation_service
        self._rebuild_state = rebuild_state
        self._waiting_line = waiting_line
        self._company_repository = company_repository

    @property
    def target_version(self) -> str:
        return self._version

    async def is_active(self, version: str | None = None) -> bool:
        """Return whether the target version has finished its rebuild gate."""
        return bool(await self._rebuild_state.is_complete(version or self._version))

    async def run(self, company_ids: Sequence[Any] | None = None) -> dict[str, Any]:
        """Run one rolling pass; failed companies stay eligible for a retry."""
        await self._rebuild_state.ensure_pending(self._version)
        await self._rebuild_state.mark_running(self._version)

        tenants = await self._resolve_companies(company_ids)
        batches = [
            tenants[index : index + self._batch_size]
            for index in range(0, len(tenants), self._batch_size)
        ]
        failed, deferred, rows_written = await self._process_batches(batches)

        status = 'complete'
        if failed or deferred:
            status = 'incomplete'
        else:
            await self._rebuild_state.mark_complete(self._version)
        return {
            'status': status,
            'version': self._version,
            'companies': tenants,
            'batches': batches,
            'rows_written': rows_written,
            'failed': failed,
            'deferred': deferred,
        }

    async def _process_batches(self, batches: list[list[str]]) -> tuple[list[str], list[str], int]:
        failed: list[str] = []
        deferred: list[str] = []
        rows_written = 0
        for batch in batches:
            for tenant in batch:
                try:
                    result = await self._run_company(tenant)
                except Exception:  # noqa: BLE001 - one company must not abort the pass
                    failed.append(tenant)
                    continue
                if getattr(result, 'busy', False):
                    deferred.append(tenant)
                    continue
                rows_written += int(result)
        return failed, deferred, rows_written

    async def _resolve_companies(self, company_ids: Sequence[Any] | None) -> list[str]:
        if company_ids is not None:
            values = [_company_id(value) for value in company_ids]
        elif self._company_repository is not None:
            listing = getattr(self._company_repository, 'list_companies', None) or getattr(
                self._company_repository, 'list_all', None
            )
            if not callable(listing):
                raise ValueError('company_ids are required when no listing port is available')
            try:
                companies = await listing()
            except TypeError:
                companies = await listing(None)
            values = [_company_id(value) for value in companies or []]
        else:
            raise ValueError('company_ids are required when no company repository is available')
        return sorted({value for value in values if value})

    async def _run_company(self, company_id: str) -> Any:
        async def work() -> Any:
            return await self._recompute(company_id)

        if self._waiting_line is None:
            return await work()
        return await self._waiting_line.run(company_id, work, priority=self._priority)

    async def _recompute(self, company_id: str) -> int:
        metrics = await self._metric_repository.list_metrics(company_id)
        computed = self._computation_service.compute_all(metrics)
        rows: list[dict[str, Any]] = []
        for row in computed or []:
            prepared = dict(row)
            prepared.setdefault('company_id', company_id)
            prepared['computation_rule_version'] = self._version
            rows.append(prepared)
        if not rows:
            return 0
        await self._kpi_repository.upsert_batch(rows, company_id=company_id)
        return len(rows)


__all__ = ['KpiRebuildJob']
