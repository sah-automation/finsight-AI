from pydantic import Field

from .strict_base_model import StrictBaseModel


class CacheConfig(StrictBaseModel):
    answer_enabled: bool = True
    clear_on_upload: bool = True
    ttl_seconds: int = Field(ge=1, default=3600)
