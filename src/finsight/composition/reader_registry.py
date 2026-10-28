"""Compatibility module for reader registry/factory helpers."""

from __future__ import annotations

from .container import *  # noqa: F403
from .container import (
    ReaderFactory,
    ReaderFactoryInstance,
    ReaderRegistry,
    build_reader,
    build_reader_factory,
    build_reader_map,
    build_reader_registry,
    build_readers,
    create_reader,
    create_reader_registry,
    get_reader,
    get_reader_registry,
)

__all__ = [
    'ReaderFactory',
    'ReaderFactoryInstance',
    'ReaderRegistry',
    'build_reader',
    'build_reader_factory',
    'build_reader_map',
    'build_reader_registry',
    'build_readers',
    'create_reader',
    'create_reader_registry',
    'get_reader',
    'get_reader_registry',
]
