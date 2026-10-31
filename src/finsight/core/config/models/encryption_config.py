from __future__ import annotations

from typing import Literal

from .strict_base_model import StrictBaseModel


class EncryptionConfig(StrictBaseModel):
    key_mode: Literal['aws_managed', 'kms_customer'] = 'aws_managed'
    kms_key_alias: str = ''
