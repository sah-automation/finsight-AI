from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class RouterConfig(StrictBaseModel):
    num_retries: int = Field(ge=0)
    retry_after: int = Field(ge=1)
    allowed_fails: int = Field(ge=0)
    cooldown_time: int = Field(ge=1)
