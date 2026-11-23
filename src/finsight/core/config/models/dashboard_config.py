"""Dashboard Configuration models."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .default_layout import DefaultLayout  # noqa: TC001
from .strict_base_model import StrictBaseModel


class DashboardConfig(StrictBaseModel):
    """Dashboard configuration section."""

    auto_refresh_seconds: Annotated[int, Field(ge=5, le=300)] = 30
    default_layout: DefaultLayout
    staleness_badge_enabled: bool = True
