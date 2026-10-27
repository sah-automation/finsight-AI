"""Composition helpers for the onboarding use case."""

from __future__ import annotations

from typing import Any

from finsight.application.onboarding import CreateCompany


def build_onboarding_use_case(**kwargs: Any) -> CreateCompany:
    """Build an onboarding use case instance."""
    return CreateCompany(**kwargs)


def get_onboarding_use_case(**kwargs: Any) -> CreateCompany:
    """Return an onboarding use case instance."""
    return CreateCompany(**kwargs)


def create_onboarding_use_case(**kwargs: Any) -> CreateCompany:
    """Alias for build_onboarding_use_case."""
    return build_onboarding_use_case(**kwargs)
