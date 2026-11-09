from pydantic import model_validator

from .strict_base_model import StrictBaseModel


class ModelsAnswerConfig(StrictBaseModel):
    primary: str
    primary_fallbacks: list[str]
    cheap: str
    cheap_fallbacks: list[str]

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
        return self
