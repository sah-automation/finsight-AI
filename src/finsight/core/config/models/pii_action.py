from enum import StrEnum


class PiiAction(StrEnum):
    MASK = 'mask'
    BLOCK = 'block'
    LOG = 'log'
