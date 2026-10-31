from pydantic import Field, model_validator

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

    @model_validator(mode='after')
    def validate_chains(self) -> 'ModelsAnswerConfig':
        for name, primary, fallbacks in (
            ('primary', self.primary, self.primary_fallbacks),
            ('cheap', self.cheap, self.cheap_fallbacks),
        ):
            chain_length = 3
            if len(fallbacks) != chain_length:
                raise ValueError(f'{name} chain must have exactly 3 fallbacks')
            chain = [primary, *fallbacks]
            if len(set(chain)) != len(chain):
                raise ValueError(f'all models in the {name} chain must be different')
            if 'self_hosted' not in fallbacks[-1]:
                raise ValueError(
                    f'fallback 3 in the {name} chain must be a self-hosted, in-region model'
                )
        return self
