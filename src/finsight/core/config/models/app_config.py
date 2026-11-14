from .environment import Environment
from .strict_base_model import (
    StrictBaseModel,
)


class AppConfig(StrictBaseModel):
    name: str
    version: str
    environment: Environment
