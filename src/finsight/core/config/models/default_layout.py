"""Default Layout model."""

from __future__ import annotations

from .default_layout_chart import DefaultLayoutChart  # noqa: TC001
from .strict_base_model import StrictBaseModel


class DefaultLayout(StrictBaseModel):
    """Default dashboard layout."""

    kpi_codes: list[str]
    charts: list[DefaultLayoutChart]
