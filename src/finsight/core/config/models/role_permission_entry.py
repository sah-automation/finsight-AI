from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class RolePermissionEntry(StrictBaseModel):
    categories: dict[str, list[str]] = Field(default_factory=dict)
    role_actions: list[str] = Field(default_factory=list)
