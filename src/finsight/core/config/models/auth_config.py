from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class AuthConfig(StrictBaseModel):
    user_pool_id: str
    client_id: str
    region: str
    jwks_cache_ttl_seconds: int = Field(ge=1)
    token_verification_clock_skew_seconds: int = Field(ge=0)
