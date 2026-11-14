from pydantic import BaseModel, ConfigDict

_MAX_FALLBACK_MODELS = 3
_MIN_PRODUCTION_TRACE_SAMPLE_RATE = 0.01
_MIN_ANSWER_CACHE_TTL_SECONDS = 300
_MIN_ROLE_CACHE_TTL_SECONDS = 60


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra='forbid',
        validate_assignment=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )
