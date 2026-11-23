"""Apply caller visibility to dashboard layout records and field lists."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from finsight.domain.value_objects.layout_chart import LayoutChart

from ._dashboard_layout_repository_fields import json_fields

if TYPE_CHECKING:
    from collections.abc import Mapping

    from finsight.domain.value_objects.layout_record import LayoutRecord
    from finsight.domain.value_objects.visible_ids import VisibleIds


def visible_json_fields(
    fields: Mapping[str, list[Any]], visible_ids: VisibleIds
) -> dict[str, list[Any]]:
    """Drop ids outside the visible set, preserving stored order."""
    allowed_codes = set(visible_ids.kpi_codes)
    allowed_charts = set(visible_ids.chart_ids)
    return {
        'kpi_codes': [code for code in fields['kpi_codes'] if code in allowed_codes],
        'charts': [chart for chart in fields['charts'] if chart['chart_id'] in allowed_charts],
    }


def filter_record(record: LayoutRecord, visible_ids: VisibleIds) -> LayoutRecord:
    """Return only the ids the caller may see, keeping version and timestamp."""
    fields = visible_json_fields(json_fields(record), visible_ids)
    return replace(
        record,
        kpi_codes=tuple(fields['kpi_codes']),
        charts=tuple(LayoutChart(**chart) for chart in fields['charts']),
    )
