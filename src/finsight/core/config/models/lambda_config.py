from __future__ import annotations

from pydantic import Field

from .strict_base_model import StrictBaseModel


class LambdaConfig(StrictBaseModel):
    snapstart_enabled: bool = False
    keep_warm_ping: bool = False
    weekly_republish: bool = False
    question_provisioned_concurrency: int = Field(ge=0, default=0)
