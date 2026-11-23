"""Default Layout Chart model."""

from __future__ import annotations

from typing import Literal

from .strict_base_model import StrictBaseModel

LayoutSpan = Literal['full', 'half']


class DefaultLayoutChart(StrictBaseModel):
    """Chart entry in default layout."""

    chart_id: str
    span: LayoutSpan
