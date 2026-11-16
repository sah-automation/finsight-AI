from pydantic import Field, model_validator

from .alert_config import AlertConfig
from .log_format import LogFormat
from .strict_base_model import (
    StrictBaseModel,
)


class ObservabilityConfig(StrictBaseModel):
    log_level: str
    log_format: LogFormat
    trace_sample_rate: float = Field(ge=0.0, le=1.0)
    service_name: str
    # CloudWatch (pilot) backend
    cloudwatch_otlp_endpoint: str = ''
    cloudwatch_otlp_headers: dict[str, str] = Field(default_factory=dict)
    # OTLP Endpoint (standard) backend
    otlp_endpoint_endpoint: str = ''
    otlp_endpoint_headers: dict[str, str] = Field(default_factory=dict)
    # Legacy single endpoint (for backward compatibility)
    otlp_endpoint: str = ''
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    alerts: AlertConfig

    @model_validator(mode='after')
    def validate_production_trace_rate(self) -> 'ObservabilityConfig':
        # Will be checked in context of app environment if needed
        return self

    def get_endpoint_for_backend(self, backend: str) -> str:
        """Get the OTLP endpoint for the specified backend."""
        if backend == 'cloudwatch':
            return self.cloudwatch_otlp_endpoint or self.otlp_endpoint
        if backend == 'otlp_endpoint':
            return self.otlp_endpoint_endpoint or self.otlp_endpoint
        return self.otlp_endpoint

    def get_headers_for_backend(self, backend: str) -> dict[str, str]:
        """Get the OTLP headers for the specified backend."""
        if backend == 'cloudwatch':
            return self.cloudwatch_otlp_headers or self.otlp_headers
        if backend == 'otlp_endpoint':
            return self.otlp_endpoint_headers or self.otlp_headers
        return self.otlp_headers
