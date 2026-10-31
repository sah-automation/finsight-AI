from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = 'development'
    TEST = 'test'
    STAGING = 'staging'
    PRODUCTION = 'production'
