from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class AlertConfig(StrictBaseModel):
    fallback_model_3_used: bool
    reranker_down: bool
    embedding_retries_exceeded: int = Field(ge=1)
    job_in_retry_list: bool
    role_cache_stale_seconds: int = Field(ge=1)
