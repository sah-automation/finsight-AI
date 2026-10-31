from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class DatabaseConfig(StrictBaseModel):
    engine: str = 'aurora_postgres'
    min_capacity_acu: float = Field(ge=0.0, default=0.0)
    auto_pause_minutes: int = Field(ge=0, default=30)
    connect_retry_attempts: int = Field(ge=1, default=5)
    connect_retry_wait_seconds: int = Field(ge=0, default=5)
    show_waking_message: bool = True
    rds_proxy_enabled: bool = False
    rds_proxy_max_connections_percent: int = Field(ge=0, le=100, default=80)
    standby_reader_enabled: bool = False

    @model_validator(mode='after')
    def validate_min_capacity_acu(self) -> 'DatabaseConfig':
        value = self.min_capacity_acu
        # Aurora Serverless v2 allows 0 (auto-pause) or 0.5 and above.
        min_capacity = 0.5
        if value != 0.0 and value < min_capacity:
            raise ValueError('min_capacity_acu must be 0 or 0.5 or higher')
        if self.rds_proxy_enabled and value == 0.0:
            raise ValueError(
                'rds_proxy_enabled is rejected with min_capacity_acu 0 until a test proves Aurora still pauses'  # noqa: E501
            )
        if self.standby_reader_enabled and value == 0.0:
            raise ValueError(
                'standby_reader_enabled is rejected with min_capacity_acu 0 until a test proves they work together'  # noqa: E501
            )
        return self
