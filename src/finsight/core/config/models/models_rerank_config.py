from pydantic import Field

from .strict_base_model import StrictBaseModel


class ModelsRerankConfig(StrictBaseModel):
    primary: str = 'self_hosted/cross_encoder_small'
    timeout_ms: int = Field(ge=100, le=1000, default=600)
    on_failure: str = 'search_order'
