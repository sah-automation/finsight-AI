"""Materialise KPI rows during ingestion after metric extraction."""

from __future__ import annotations

from typing import Any


def _ctx_get(context: Any, name: str, default: Any = None) -> Any:
    if isinstance(context, dict):
        return context.get(name, default)
    return getattr(context, name, default)


def _ctx_set(context: Any, name: str, value: Any) -> None:
    if isinstance(context, dict):
        context[name] = value
        return
    try:
        setattr(context, name, value)
    except Exception:  # noqa: BLE001
        if isinstance(context, dict):
            context[name] = value


class KpiMaterialisationStep:
    """Compute and persist KPI rows for the current document version."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        metric_repository: Any = None,
        kpi_repository: Any = None,
        computation_service: Any = None,
        change_event_publisher: Any = None,
        delta_tracking: bool = True,
        config: Any = None,
        **_: Any,
    ) -> None:
        self._metric_repository = metric_repository
        self._kpi_repository = kpi_repository
        self._computation_service = computation_service
        self._change_event_publisher = change_event_publisher
        self._config = config
        self._delta_tracking = self._resolve_delta_tracking(delta_tracking, config)
        self._previous_version_id: Any | None = None

    @staticmethod
    def _resolve_delta_tracking(delta_tracking: bool, config: Any) -> bool:
        if config is not None:
            documents = getattr(config, 'documents', None)
            if documents is not None and getattr(documents, 'delta_tracking', None) is not None:
                return bool(documents.delta_tracking)
        return bool(delta_tracking)

    async def run(self, context: Any = None, /, **kwargs: Any) -> Any:
        """Materialise KPI rows for the version in context and store them in-repo."""
        ctx = context if context is not None else dict(kwargs)
        company_id = kwargs.get('company_id', _ctx_get(ctx, 'company_id'))
        document_version_id = self._document_version_id(ctx, kwargs)
        document_id = kwargs.get('document_id', _ctx_get(ctx, 'document_id'))

        # Load current version's metrics
        metrics = await self._load_metrics(ctx, company_id, document_version_id)

        # Apply delta filtering if enabled
        if self._delta_tracking:
            previous_metrics = await self._load_previous_metrics(
                company_id, document_id, document_version_id
            )
            metrics, full_recompute = self._filter_metrics_for_delta(metrics, previous_metrics)
            if full_recompute:
                # Reload all current metrics for full recompute
                metrics = await self._load_metrics(ctx, company_id, document_version_id)

        rows = self._compute_rows(metrics)
        await self._upsert_rows(rows, company_id)
        result = self._result(rows, company_id, document_id, document_version_id)
        self._store_result(ctx, result)
        return ctx

    @staticmethod
    def _document_version_id(context: Any, kwargs: dict[str, Any]) -> Any:
        return kwargs.get(
            'document_version_id',
            kwargs.get(
                'version_id',
                _ctx_get(context, 'document_version_id', _ctx_get(context, 'version_id')),
            ),
        )

    async def _upsert_rows(self, rows: list[dict[str, Any]], company_id: Any) -> None:
        if not rows or self._kpi_repository is None:
            return
        upsert = getattr(self._kpi_repository, 'upsert_batch', None)
        if callable(upsert):
            await upsert(rows, company_id=company_id)

    def _result(
        self,
        rows: list[dict[str, Any]],
        company_id: Any,
        document_id: Any,
        document_version_id: Any,
    ) -> dict[str, Any]:
        codes = sorted({str(row.get('kpi_code', '')) for row in rows if row.get('kpi_code')})
        periods = sorted({str(row.get('period', '')) for row in rows if row.get('period')})
        return {
            'kpi_rows': rows,
            'kpi_count': len(rows),
            'kpi_codes': codes,
            'periods': periods,
            'company_id': company_id,
            'document_id': document_id,
            'document_version_id': document_version_id,
            'delta_tracking': self._delta_tracking,
        }

    @staticmethod
    def _store_result(context: Any, result: dict[str, Any]) -> None:
        _ctx_set(context, 'kpi_rows', result['kpi_rows'])
        _ctx_set(context, 'kpi_count', result['kpi_count'])
        _ctx_set(context, 'kpi_codes', result['kpi_codes'])
        _ctx_set(context, 'kpi_periods', result['periods'])
        _ctx_set(context, 'kpi_materialisation', result)

    async def _load_metrics(
        self, context: Any, company_id: Any, document_version_id: Any
    ) -> list[Any]:
        cached = _ctx_get(context, 'metrics')
        if isinstance(cached, list) and cached:
            # Use in-context metrics when present; they are the extracted metrics for this run.
            return list(cached)
        repo = self._metric_repository
        if repo is None:
            return []
        list_metrics = getattr(repo, 'list_metrics', None)
        if not callable(list_metrics):
            return []
        try:
            rows = await list_metrics(company_id, document_version_id=document_version_id)
        except TypeError:
            rows = await list_metrics(company_id, version_id=document_version_id)
        return list(rows or [])

    async def _load_previous_metrics(
        self, company_id: Any, document_id: Any, document_version_id: Any
    ) -> list[Any]:
        """Load metrics from the previous committed version of the same document."""
        repo = self._metric_repository
        if repo is None:
            return []
        list_metrics = getattr(repo, 'list_metrics', None)
        if not callable(list_metrics):
            return []
        # Try to find the previous committed version
        previous_version_id = await self._find_previous_committed_version(
            company_id, document_id, document_version_id
        )
        if previous_version_id is None:
            return []
        try:
            rows = await list_metrics(company_id, document_version_id=previous_version_id)
        except TypeError:
            rows = await list_metrics(company_id, version_id=previous_version_id)
        return list(rows or [])

    async def _find_previous_committed_version(
        self, company_id: Any, document_id: Any, _current_version_id: Any
    ) -> Any | None:
        """Find the previous committed version of the same document."""
        # Try to get it from context first (set by pipeline)
        previous = getattr(self, '_previous_version_id', None)
        if previous is not None:
            return previous
        # Fallback: try to get from document repository if available
        # The pipeline worker sets this when it runs supersede_previous_versions
        return None

    def _filter_metrics_for_delta(
        self, current_metrics: list[Any], previous_metrics: list[Any]
    ) -> tuple[list[Any], bool]:
        """
        Filter current metrics to only those that are new, changed, or whose removal affects KPIs.
        Returns (filtered_metrics, should_compute_all) where should_compute_all is True
        if a full recompute is needed (e.g., no previous metrics to compare).
        """
        if not previous_metrics:
            return current_metrics, True
        if not current_metrics:
            return [], False

        # Build lookup maps by (name, period, currency, units, document_id)
        def metric_key(m: Any) -> tuple[str, str, str, str, str]:
            return (
                getattr(m, 'name', None) or getattr(m, 'metric_name', None) or '',
                getattr(m, 'period', None) or getattr(m, 'fiscal_period', None) or '',
                getattr(m, 'currency', None) or '',
                getattr(m, 'units', None) or getattr(m, 'unit', None) or '',
                getattr(m, 'document_id', None) or '',
            )

        prev_map = {metric_key(m): m for m in previous_metrics}
        changed_metrics: list[Any] = []

        for metric in current_metrics:
            key = metric_key(metric)
            prev = prev_map.get(key)
            if prev is None:
                # New metric
                changed_metrics.append(metric)
            else:
                # Check if value changed
                curr_val = str(getattr(metric, 'value', '') or '')
                prev_val = str(getattr(prev, 'value', '') or '')
                if curr_val != prev_val:
                    changed_metrics.append(metric)

        # Also include metrics that were removed (to trigger recompute of dependent KPIs)
        # We can't include removed metrics directly since they don't exist in current,
        # but we track that we need to recompute KPIs that depend on them.
        # For now, if there are removed metrics, we do a full recompute for safety.
        current_keys = {metric_key(m) for m in current_metrics}
        removed_keys = set(prev_map.keys()) - current_keys
        if removed_keys:
            return current_metrics, True

        return changed_metrics, False

    def _compute_rows(self, metrics: list[Any]) -> list[dict[str, Any]]:
        service = self._computation_service
        if service is None:
            return []
        compute_all = getattr(service, 'compute_all', None)
        if callable(compute_all):
            rows = compute_all(metrics)
        else:
            rows = self._compute_all_via_methods(service, metrics)
        return [dict(row) for row in (rows or []) if isinstance(row, dict)]

    @staticmethod
    def _compute_all_via_methods(service: Any, metrics: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in (
            'compute_revenue',
            'compute_gross_margin',
            'compute_net_margin',
            'compute_operating_expenses',
            'compute_cash_flow',
            'compute_burn_rate',
            'compute_runway',
            'compute_dso',
            'compute_dpo',
            'compute_budget_vs_actual',
        ):
            method = getattr(service, name, None)
            if callable(method):
                rows.extend(list(method(metrics) or []))
        spread = getattr(service, 'spread_quarterly', None)
        if callable(spread):
            rows = list(spread(rows) or [])
        mark_conflicts = getattr(service, 'mark_conflicts', None)
        if callable(mark_conflicts):
            rows = list(mark_conflicts(rows) or [])
        apply_display = getattr(service, 'apply_display_labels', None)
        if callable(apply_display):
            rows = list(apply_display(rows) or [])
        return [dict(row) for row in rows if isinstance(row, dict)]
