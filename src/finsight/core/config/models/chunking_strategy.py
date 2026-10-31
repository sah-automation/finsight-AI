from __future__ import annotations

from enum import StrEnum


class ChunkingStrategy(StrEnum):
    SEMANTIC = 'semantic'
    FIXED = 'fixed'
    RECURSIVE = 'recursive'
