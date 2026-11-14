from .chunking_config import ChunkingConfig
from .strict_base_model import (
    StrictBaseModel,
)
from .tesseract_config import TesseractConfig
from .textract_config import TextractConfig


class ReadersConfig(StrictBaseModel):
    priority: list[str]
    textract: TextractConfig
    tesseract: TesseractConfig
    chunking: ChunkingConfig
