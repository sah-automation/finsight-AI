"""Partition-related enums."""

from __future__ import annotations

from enum import StrEnum


class PartitionStatus(StrEnum):
    """Partition creation status."""

    CREATING = 'creating'
    READY = 'ready'
    FAILED = 'failed'
