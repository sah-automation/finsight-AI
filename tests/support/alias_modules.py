"""Compatibility shim exposing pass-through detector helpers."""

from __future__ import annotations

from tests.support.ast_inspection import *  # noqa: F403
from tests.support.ast_inspection import (
    count_passthrough_modules,
    find_alias_modules,
    find_pass_through_modules,
    find_passthrough_modules,
    find_passthroughs,
    find_reexport_modules,
    is_alias_module,
    is_passthrough_module,
    is_reexport_module,
)

__all__ = [
    'count_passthrough_modules',
    'find_alias_modules',
    'find_pass_through_modules',
    'find_passthrough_modules',
    'find_passthroughs',
    'find_reexport_modules',
    'is_alias_module',
    'is_passthrough_module',
    'is_reexport_module',
]
