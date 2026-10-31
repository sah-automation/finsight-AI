"""Approved model configuration."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import AliasChoices, Field, field_validator

from .strict_base_model import StrictBaseModel


class ApprovedModelConfig(StrictBaseModel):
    """A model explicitly approved for use in a given environment/region."""

    model_id: str = Field(
        validation_alias=AliasChoices(
            'model_id',
            'model',
            'id',
            'name',
            'model_name',
        )
    )
    provider: str | None = None
    regions: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            'regions',
            'region',
            'allowed_regions',
            'locations',
        ),
    )
    approved: bool = True

    @field_validator('regions', mode='before')
    @classmethod
    def _coerce_regions(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Mapping):
            return [str(key) for key in value]
        return [str(item) for item in value]

    @field_validator('model_id', mode='before')
    @classmethod
    def _coerce_model_id(cls, value: object) -> str:
        return str(value).strip()

    def is_approved_for(self, region: str | None) -> bool:
        if not self.approved:
            return False
        if region is None or not self.regions:
            return True
        return region in self.regions
