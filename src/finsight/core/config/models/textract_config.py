from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class TextractConfig(StrictBaseModel):
    async_enabled: bool
    poll_interval_seconds: int = Field(ge=1)
    max_poll_attempts: int = Field(ge=1)
    feature_types: list[str]
    region: str
