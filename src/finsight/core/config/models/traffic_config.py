from pydantic import Field

from .strict_base_model import StrictBaseModel


class TrafficConfig(StrictBaseModel):
    lambda_reserved_concurrency: int = Field(ge=0, default=20)
    ingestion_max_concurrency: int = Field(ge=1, default=4)
    db_connections_per_request: int = Field(ge=1, default=3)
    db_pool_size_per_function: int = Field(ge=1, default=3)
    db_pool_timeout_seconds: int = Field(ge=1, default=10)
    aurora_max_capacity_acu: int = Field(ge=1, default=4)
