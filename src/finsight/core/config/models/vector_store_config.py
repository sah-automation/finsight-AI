from pydantic import Field, model_validator

from .strict_base_model import (
    StrictBaseModel,
)


class VectorStoreConfig(StrictBaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    username: str
    password: str
    ssl_mode: str
    pool_size: int = Field(ge=1)
    max_overflow: int = Field(ge=0)
    pool_timeout_seconds: int = Field(ge=1)
    pool_recycle_seconds: int = Field(ge=1)
    hnsw_ef_search: int = Field(ge=1)
    hnsw_ef_construction: int = Field(ge=1)
    hnsw_m: int = Field(ge=1)

    @model_validator(mode='after')
    def validate_pool(self) -> 'VectorStoreConfig':
        if self.max_overflow > self.pool_size:
            raise ValueError('max_overflow must be <= pool_size')
        return self
