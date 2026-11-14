from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class MeteringConfig(StrictBaseModel):
    table_name: str
    flush_interval_seconds: int = Field(ge=1, default=60)
    batch_size: int = Field(ge=1, default=100)
    price_table: str = 'config/prices.yaml'
    shared_cost_split: str = 'requests_and_runtime'
    reconcile_tolerance_percent: int = Field(ge=1, le=25, default=10)
