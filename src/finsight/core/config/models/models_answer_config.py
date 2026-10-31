from pydantic import Field

from .strict_base_model import StrictBaseModel


class ModelsAnswerConfig(StrictBaseModel):
    primary: str = 'provider_a/model_strong'
    primary_fallbacks: list[str] = Field(
        default_factory=lambda: [
            'provider_b/model_strong',
            'provider_c/model_strong',
            'self_hosted/open_model_small',
        ]
    )
    cheap: str = 'provider_a/model_small'
    cheap_fallbacks: list[str] = Field(
        default_factory=lambda: [
            'provider_b/model_small',
            'provider_c/model_small',
            'self_hosted/open_model_small',
        ]
    )
