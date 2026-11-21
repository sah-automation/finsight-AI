"""Web Configuration models."""

from __future__ import annotations

from .strict_base_model import StrictBaseModel
from .vercel_config import VercelConfig  # noqa: TC001


class WebConfig(StrictBaseModel):
    """Web configuration section."""

    vercel: VercelConfig
