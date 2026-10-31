from __future__ import annotations

from pydantic import Field

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
