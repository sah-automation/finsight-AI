"""Vercel Configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .strict_base_model import StrictBaseModel

PreviewApiTarget = Literal['mock']


class VercelConfig(StrictBaseModel):
    """Vercel deployment configuration section."""

    sync_enabled: bool = True
    preview_api_target: PreviewApiTarget = 'mock'
    log_forwarding_enabled: bool = True
    log_retention_days: int = Field(gt=0, default=30)
    never_log_file: str = 'config/never_log.yaml'
    otlp_log_group: str = Field(min_length=1, default='/aws/finsight/web-prod')
