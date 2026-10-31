"""TableReader adapter for table-sensitive pages."""

from __future__ import annotations

from typing import Any

from .base_reader import BaseReader


def _init__(self: Any, *args: Any, **kwargs: Any) -> Any:
    delegate = kwargs.pop('delegate', None)
    if delegate is None:
        delegate = kwargs.pop('wrapped_reader', None)
    if delegate is None:
        delegate = kwargs.pop('wrapped', None)
    if delegate is None:
        delegate = kwargs.pop('reader', None)
    if delegate is None:
        delegate = kwargs.pop('underlying_reader', None)
    if delegate is None:
        delegate = kwargs.pop('table_reader_instance', None)
    if delegate is None:
        delegate = kwargs.pop('layout_reader', None)
    underlying_name: Any = None
    if delegate is None:
        for key in (
            'table_reader',
            'table_reader_name',
            'backend',
            'engine',
        ):
            if key in kwargs:
                candidate = kwargs.pop(key)
                if candidate is not None:
                    delegate = candidate
                    break
    if delegate is None:
        for arg in args:
            if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
                delegate = arg
                break
            if isinstance(arg, str):
                underlying_name = arg
                break

    if isinstance(delegate, str):
        underlying_name = delegate
        delegate = None

    passed_config = None
    if 'config' in kwargs:
        passed_config = kwargs.pop('config')
    if 'settings' in kwargs and passed_config is None:
        passed_config = kwargs.pop('settings')
    if 'configuration' in kwargs and passed_config is None:
        passed_config = kwargs.pop('configuration')
    session = kwargs.pop('session', kwargs.pop('db_session', None))

    self._delegate = delegate
    self._delegate_name = underlying_name
    self._passed_config = passed_config
    self._config = passed_config
    self._session = session
    BaseReader.__init__(self, config=passed_config, session=session)

    self._minimum_table_lines = int(kwargs.pop('min_table_lines', 0) or 0)
    for key, value in kwargs.items():
        if key not in self.__dict__:
            setattr(self, key, value)
