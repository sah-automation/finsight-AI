"""Computation status of a code-computed KPI row."""

from __future__ import annotations

from enum import StrEnum


class ComputationStatus(StrEnum):
    """Machine state carried by every KPI row."""

    COMPUTED = 'computed'
    ESTIMATED = 'estimated'
    NEEDS_REVIEW = 'needs_review'


__all__ = ['ComputationStatus']
