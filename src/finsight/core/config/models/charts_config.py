"""Charts Configuration models."""

from __future__ import annotations

from pydantic import Field

from .chart_spec import ChartSpec, ExportFormat  # noqa: TC001
from .strict_base_model import StrictBaseModel


def _default_export_formats() -> list[ExportFormat]:
    return ['png', 'pdf']


class ChartsConfig(StrictBaseModel):
    """Charts configuration section."""

    specs: dict[str, ChartSpec]
    export_formats: list[ExportFormat] = Field(default_factory=_default_export_formats)
