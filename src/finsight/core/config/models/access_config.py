from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class AccessConfig(StrictBaseModel):
    roles: list[str] = Field(
        default_factory=lambda: [
            'executive_leadership',
            'corporate_finance_planners',
            'audit_compliance',
            'system_admin',
        ]
    )
    permissions_file: str = 'config/permissions.yaml'
    role_cache_seconds_privileged: int = Field(ge=0, default=0)
    users_per_company_max: int = Field(ge=1, default=10)
