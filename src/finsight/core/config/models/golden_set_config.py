"""Golden Set Configuration models."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .strict_base_model import StrictBaseModel


class GoldenSetConfig(StrictBaseModel):
    """Golden set configuration section."""

    kpi_questions_path: Annotated[str, Field(min_length=1)] = (
        'tests/golden/questions/phase2_kpi.yaml'
    )
