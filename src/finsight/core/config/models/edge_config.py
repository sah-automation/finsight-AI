from __future__ import annotations

from .strict_base_model import StrictBaseModel


class EdgeConfig(StrictBaseModel):
    http3_enabled: bool = True
