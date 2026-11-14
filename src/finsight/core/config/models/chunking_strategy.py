from enum import StrEnum


class ChunkingStrategy(StrEnum):
    SEMANTIC = 'semantic'
    FIXED = 'fixed'
    RECURSIVE = 'recursive'
