from typing import Literal

from pydantic import model_validator

from .strict_base_model import StrictBaseModel


class EncryptionConfig(StrictBaseModel):
    key_mode: Literal['aws_managed', 'kms_customer'] = 'aws_managed'
    kms_key_alias: str = ''

    @model_validator(mode='after')
    def validate_kms_alias(self) -> 'EncryptionConfig':
        if self.key_mode == 'kms_customer' and not self.kms_key_alias.strip():
            raise ValueError('kms_key_alias is required when key_mode is kms_customer')
        return self
