from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class ModelsAnswerConfig(StrictBaseModel):
    primary: str = 'gemini/gemini-1.5-pro'
    primary_fallbacks: list[str] = Field(
        default_factory=lambda: [
            'nvidia_nim/meta/llama-3.1-70b-instruct',
            'groq/llama-3.3-70b-versatile',
            'self_hosted/open_model_small',
        ]
    )
    cheap: str = 'groq/llama-3.1-8b-instant'
    cheap_fallbacks: list[str] = Field(
        default_factory=lambda: [
            'nvidia_nim/meta/llama-3.1-8b-instruct',
            'gemini/gemini-1.5-flash',
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
