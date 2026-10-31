from pydantic import Field

from .strict_base_model import StrictBaseModel


class ProtectionConfig(StrictBaseModel):
    waf_enabled: bool = False
    api_rate_limit_per_second: int = Field(ge=1, default=10)
    api_burst_limit: int = Field(ge=1, default=20)
