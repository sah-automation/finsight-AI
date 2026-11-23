"""Resolve chart variance inputs from source metrics (issue #380)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.ports.metric_repository import MetricRepository

from finsight.domain.services._kpi_budget import compute_budget_vs_actual_totals


class ChartVarianceResolver:
    """Enrich variance rows with budget and actual totals."""

    def __init__(self, metric_repository: MetricRepository) -> None:
        self._metric_repository = metric_repository

    async def enrich(
        self,
        company_id: str,
        rows: Sequence[dict[str, Any]],
        variance_kpi_codes: Sequence[str],
    ) -> list[dict[str, Any]]:
        if not variance_kpi_codes:
            return [dict(row) for row in rows]

        needs = self._rows_needing_enrichment(rows, variance_kpi_codes)
        if not needs:
            return [dict(row) for row in rows]

        version_ids = self._version_ids(needs)
        if not version_ids:
            return [dict(row) for row in rows]

        metrics = await self._metric_repository.list_metrics(
            company_id,  # type: ignore[arg-type]
            version_ids=list(version_ids),
        )
        actual_total, budget_total, name = compute_budget_vs_actual_totals(metrics)

        enriched = [dict(row) for row in rows]
        for idx, row in needs:
            self._apply_totals(enriched[idx], row, actual_total, budget_total, name)
        return enriched

    def _rows_needing_enrichment(
        self,
        rows: Sequence[dict[str, Any]],
        variance_kpi_codes: Sequence[str],
    ) -> list[tuple[int, dict[str, Any]]]:
        allowed = set(variance_kpi_codes)
        needs: list[tuple[int, dict[str, Any]]] = []
        for idx, row in enumerate(rows):
            if _text(row.get('kpi_code')) in allowed and (
                row.get('actual') is None or row.get('budget') is None
            ):
                needs.append((idx, row))
        return needs

    def _version_ids(
        self,
        needs: list[tuple[int, dict[str, Any]]],
    ) -> set[str]:
        version_ids: set[str] = set()
        for _, row in needs:
            version_id = _text(row.get('document_version_id'))
            if version_id:
                version_ids.add(version_id)
        return version_ids

    def _apply_totals(
        self,
        target: dict[str, Any],
        row: dict[str, Any],
        actual_total: Any,
        budget_total: Any,
        name: Any,
    ) -> None:
        if actual_total is not None:
            target['actual'] = str(actual_total.quantize(Decimal('0.01')))
        if budget_total is not None:
            target['budget'] = str(budget_total.quantize(Decimal('0.01')))
        if name and row.get('name') is None:
            target['name'] = name


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ['ChartVarianceResolver']
