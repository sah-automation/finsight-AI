from pydantic import Field

from .strict_base_model import (
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class AnswerCacheConfig(StrictBaseModel):
    table_name: str
    ttl_seconds: int = Field(ge=_MIN_ANSWER_CACHE_TTL_SECONDS)
    key_prefix: str
    max_entry_size_bytes: int = Field(ge=1)
