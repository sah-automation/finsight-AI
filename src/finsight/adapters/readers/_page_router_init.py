"""PageRouter: route document pages to the appropriate reader."""

from __future__ import annotations

from typing import Any

from .base_reader import BaseReader

_CONTROL_KEYS = {
    'page_router_enabled',
    'enabled',
    'routed',
    'routing',
    'routing_enabled',
    'use_page_router',
    'router_enabled',
    'route',
    'reader_name',
    'force_reader',
    'page_type',
    'kind',
    'pages',
    'file_path',
    'filename',
    'file_name',
    'content_type',
    'content',
}


def _init__(self: Any, *args: Any, **kwargs: Any) -> Any:
    self.reader = None
    self.table_reader = None
    self.scan_reader = None
    self.page_router_enabled = True
    self.primary = None
    self.primary_reader = None
    self.text_reader = None
    self.ocr_reader = None
    self.enabled = True
    self.routed = True
    self._min_table_score = 0

    # Apply positional readers/config/flags.
    for arg in args:
        if isinstance(arg, bool):
            self.page_router_enabled = arg
            continue
        if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
            self._assign_reader(arg)
            continue
        self._apply_config_like(arg)

    readers = kwargs.pop('readers', None)
    if isinstance(readers, dict):
        self._apply_readers_dict(readers)

    # Named reader aliases.
    self.reader = self._coalesce_reader(
        kwargs,
        self.reader,
        'reader',
        'primary_reader',
        'primary',
        'text_reader',
        'main_reader',
        'default_reader',
        'reader_primary',
    )
    self.table_reader = self._coalesce_reader(
        kwargs,
        self.table_reader,
        'table_reader',
        'table',
        'layout_reader',
        'table_reader_instance',
    )
    self.scan_reader = self._coalesce_reader(
        kwargs, self.scan_reader, 'scan_reader', 'ocr_reader', 'ocr', 'scan_reader_instance'
    )

    # Config / settings like objects.
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
        if key in kwargs and kwargs[key] is not None:
            self._apply_config_like(kwargs.pop(key))

    # Keep convenience aliases in sync with canonical readers.
    if self.reader is None:
        self.reader = self.primary_reader
    if self.reader is not None:
        self.primary = self.reader
        self.primary_reader = self.reader
        self.text_reader = self.reader
    from .pdf_plumber_reader import PdfPlumberReader

    if self.reader is None:
        self.reader = self._default_primary()
    if self.table_reader is None:
        self.table_reader = PdfPlumberReader()
    if self.scan_reader is None:
        self.scan_reader = PdfPlumberReader()
    self.primary = self.reader
    self.primary_reader = self.reader
    self.text_reader = self.reader
    self.ocr_reader = self.scan_reader
    # Enabled flags (apply before syncing aliases).
    for key in (
        'page_router_enabled',
        'enabled',
        'routed',
        'routing_enabled',
        'use_page_router',
        'router_enabled',
    ):
        if key in kwargs and kwargs[key] is not None:
            self.page_router_enabled = bool(kwargs.pop(key))

    self.enabled = self.page_router_enabled
    self.routed = self.page_router_enabled

    threshold = kwargs.pop('min_table_lines', None)
    if threshold is not None:
        try:
            self._min_table_score = int(threshold)
        except (TypeError, ValueError):
            pass

    # Capture late-bound config/session pointers when supplied.
    if not hasattr(self, '_config'):
        for ckey in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
            if ckey in kwargs:
                self._config = kwargs.get(ckey)
                break
        else:
            self._config = None
    if not hasattr(self, '_session'):
        self._session = kwargs.get('session', kwargs.get('db_session'))
    BaseReader.__init__(self, config=self._config, session=self._session)

    # Keep any leftover attributes for compatibility.
    for key, value in kwargs.items():
        if key not in self.__dict__:
            setattr(self, key, value)
