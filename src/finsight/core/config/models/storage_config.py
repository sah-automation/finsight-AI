from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class StorageConfig(StrictBaseModel):
    documents_bucket: str
    reports_bucket: str
    backups_bucket: str
    region: str
    presigned_url_expiry_seconds: int = Field(ge=1)
    multipart_threshold_mb: int = Field(ge=1)
    multipart_chunksize_mb: int = Field(ge=1)
