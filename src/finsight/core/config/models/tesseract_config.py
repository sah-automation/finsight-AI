from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class TesseractConfig(StrictBaseModel):
    languages: list[str]
    dpi: int = Field(ge=1)
    config: str
