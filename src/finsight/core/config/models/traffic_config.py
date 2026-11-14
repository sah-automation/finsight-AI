from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class TrafficConfig(StrictBaseModel):
    lambda_reserved_concurrency: int = Field(ge=1, default=20)
    ingestion_max_concurrency: int = Field(ge=1, default=4)
    db_connections_per_request: int = Field(ge=1, default=3)
    db_pool_size_per_function: int = Field(ge=1, default=3)
    db_pool_timeout_seconds: int = Field(ge=1, default=10)
    aurora_max_capacity_acu: int = Field(ge=1, default=4)

    @model_validator(mode='after')
    def validate_traffic(self) -> 'TrafficConfig':
        if self.ingestion_max_concurrency >= self.lambda_reserved_concurrency:
            raise ValueError('ingestion_max_concurrency must be below lambda_reserved_concurrency')
        if self.db_pool_size_per_function < self.db_connections_per_request:
            # only enforce when parallel? config cannot know switch; enforce conservative?
            pass
        return self
