"""Format-driven reader selection (Slice 3.8)."""

from __future__ import annotations

from typing import Any

from .base_reader import BaseReader
from .format_reader_selector import (
    _CSV_KEYS,
    _DOCX_KEYS,
    _EXCEL_KEYS,
    _PDF_KEYS,
    _TSV_KEYS,
)


def _init__(self: Any, *args: Any, **kwargs: Any) -> Any:
    self._config = kwargs.pop('config', kwargs.pop('settings', None))
    for alias in ('configuration', 'app_config', 'ctx'):
        if alias in kwargs:
            if self._config is None:
                self._config = kwargs.pop(alias)
            else:
                kwargs.pop(alias, None)
    self._session = kwargs.pop('session', kwargs.pop('db_session', None))
    BaseReader.__init__(self, config=self._config, session=self._session)
    provided_mapping: dict[str, Any] | None = None
    pdf_reader = kwargs.pop('pdf_reader', None)
    page_router = kwargs.pop('page_router', None)
    if page_router is not None:
        pdf_reader = page_router
    # Primary reader aliases commonly used by PageRouter callers.
    for alias in (
        'reader',
        'primary_reader',
        'primary',
        'text_reader',
        'main_reader',
        'default_reader',
    ):
        if alias in kwargs:
            value = kwargs.pop(alias)
            if pdf_reader is None and hasattr(value, 'read'):
                pdf_reader = value
            # Keep non-reader attributes? Reader objects stored separately later if needed.
    table_reader_kw = kwargs.pop('table_reader', None)
    if 'table' in kwargs and table_reader_kw is None and hasattr(kwargs.get('table'), 'read'):
        table_reader_kw = kwargs.pop('table')
    elif 'table' in kwargs and not hasattr(kwargs.get('table'), 'read'):
        kwargs.pop('table', None)
    scan_reader_kw = kwargs.pop('scan_reader', None)
    if (
        scan_reader_kw is None
        and 'ocr_reader' in kwargs
        and hasattr(kwargs.get('ocr_reader'), 'read')
    ):
        scan_reader_kw = kwargs.pop('ocr_reader')
    elif 'ocr_reader' in kwargs:
        kwargs.pop('ocr_reader', None)
    page_router_enabled_kw = kwargs.pop('page_router_enabled', None)
    for flag in ('enabled', 'routed', 'routing_enabled', 'use_page_router', 'router_enabled'):
        if flag in kwargs and page_router_enabled_kw is None:
            value = kwargs.get(flag)
            if isinstance(value, bool):
                page_router_enabled_kw = value
        if flag in kwargs:
            kwargs.pop(flag, None)
    excel_reader = kwargs.pop('excel_reader', None)
    csv_reader = kwargs.pop('csv_reader', None)
    tsv_reader = kwargs.pop('tsv_reader', None)
    docx_reader = kwargs.pop('docx_reader', None)
    for key in ('pdf', 'page_router_instance', 'router', 'pdf_router'):
        if key in kwargs and pdf_reader is None:
            pdf_reader = kwargs.pop(key)
        elif key in kwargs:
            kwargs.pop(key, None)
    for key in ('excel', 'xlsx_reader', 'xlsx', 'xls_reader'):
        if key in kwargs and excel_reader is None:
            excel_reader = kwargs.pop(key)
        elif key in kwargs:
            kwargs.pop(key, None)
    for key in ('csv', 'csvdocumentreader'):
        if key in kwargs and csv_reader is None:
            csv_reader = kwargs.pop(key)
        elif key in kwargs:
            kwargs.pop(key, None)
    for key in ('tsv',):
        if key in kwargs and tsv_reader is None:
            tsv_reader = kwargs.pop(key)
        elif key in kwargs:
            kwargs.pop(key, None)
    for key in ('docx', 'docxreader', 'word', 'word_reader', 'word_document_reader'):
        if key in kwargs and docx_reader is None:
            docx_reader = kwargs.pop(key)
        elif key in kwargs:
            kwargs.pop(key, None)
    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, dict):
            if provided_mapping is None:
                provided_mapping = dict(arg)
            else:
                provided_mapping.update(arg)
            continue
        if isinstance(arg, (list, tuple)):
            for idx, item in enumerate(arg):
                if item is None:
                    continue
                if idx == 0 and pdf_reader is None:
                    pdf_reader = item
                elif idx == 1 and excel_reader is None:
                    excel_reader = item
                elif idx == 2 and csv_reader is None:
                    csv_reader = item
                elif idx == 3 and tsv_reader is None:
                    tsv_reader = item
                elif idx == 4 and docx_reader is None:
                    docx_reader = item
            continue
        if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
            if pdf_reader is None:
                pdf_reader = arg
            continue
        if hasattr(arg, 'switches') or hasattr(arg, 'app'):
            if self._config is None:
                self._config = arg
    mapping = kwargs.pop('readers', None)
    if mapping is None:
        mapping = kwargs.pop('reader_registry', None)
    if mapping is None:
        mapping = kwargs.pop('registry', None)
    if isinstance(mapping, dict):
        if provided_mapping is None:
            provided_mapping = mapping
        else:
            provided_mapping.update(mapping)
    if provided_mapping is not None:
        for key, value in provided_mapping.items():
            if value is None:
                continue
            low = str(key).strip().lower()
            if low in _PDF_KEYS:
                if pdf_reader is None:
                    pdf_reader = value
            elif low in _EXCEL_KEYS:
                if excel_reader is None:
                    excel_reader = value
            elif low in _TSV_KEYS:
                if tsv_reader is None:
                    tsv_reader = value
            elif low in _CSV_KEYS:
                if csv_reader is None:
                    csv_reader = value
            elif low in _DOCX_KEYS:
                if docx_reader is None:
                    docx_reader = value
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
        if (
            key in kwargs
            and kwargs[key] is not None
            and self._config is None
            and not hasattr(kwargs[key], 'read')
        ):
            self._config = kwargs.pop(key)
        elif key in kwargs:
            if not (
                hasattr(kwargs.get(key), 'read')
                and callable(getattr(kwargs.get(key), 'read', None))
            ):
                obj = kwargs.get(key)
                if hasattr(obj, 'switches') or hasattr(obj, 'app') or isinstance(obj, dict):
                    if self._config is None:
                        self._config = kwargs.pop(key)
                    else:
                        kwargs.pop(key, None)
    for key, value in list(kwargs.items()):
        if key not in self.__dict__:
            setattr(self, key, value)
    if pdf_reader is None and (
        table_reader_kw is not None
        or scan_reader_kw is not None
        or page_router_enabled_kw is not None
    ):
        from .page_router import PageRouter

        pr_kwargs: dict[str, Any] = {'config': self._config}
        if table_reader_kw is not None:
            pr_kwargs['table_reader'] = table_reader_kw
        if scan_reader_kw is not None:
            pr_kwargs['scan_reader'] = scan_reader_kw
        if page_router_enabled_kw is not None:
            pr_kwargs['page_router_enabled'] = page_router_enabled_kw
        try:
            pdf_reader = PageRouter(**pr_kwargs)
        except Exception:
            pdf_reader = self._default_pdf_reader()
    if pdf_reader is None:
        pdf_reader = self._default_pdf_reader()
    # Wrap a plain primary reader in a PageRouter when routed kwargs were supplied
    # so both routed and non-routed PageRouter paths are preserved.
    try:
        from .page_router import PageRouter

        is_router = isinstance(pdf_reader, PageRouter)
    except Exception:
        is_router = False
    if (not is_router) and (
        table_reader_kw is not None
        or scan_reader_kw is not None
        or page_router_enabled_kw is not None
    ):
        from .page_router import PageRouter

        pr_kwargs2: dict[str, Any] = {}
        if table_reader_kw is not None:
            pr_kwargs2['table_reader'] = table_reader_kw
        if scan_reader_kw is not None:
            pr_kwargs2['scan_reader'] = scan_reader_kw
        if page_router_enabled_kw is not None:
            pr_kwargs2['page_router_enabled'] = page_router_enabled_kw
        try:
            pdf_reader = PageRouter(pdf_reader, **pr_kwargs2)
        except Exception:
            try:
                pdf_reader = PageRouter(reader=pdf_reader, **pr_kwargs2)
            except Exception:
                pass
    try:
        from .page_router import PageRouter

        if isinstance(pdf_reader, PageRouter):
            if table_reader_kw is not None:
                pdf_reader.table_reader = table_reader_kw
            if scan_reader_kw is not None:
                pdf_reader.scan_reader = scan_reader_kw
            if page_router_enabled_kw is not None:
                pdf_reader.page_router_enabled = bool(page_router_enabled_kw)
                pdf_reader.enabled = bool(page_router_enabled_kw)
                pdf_reader.routed = bool(page_router_enabled_kw)
    except Exception:
        pass
    if excel_reader is None:
        excel_reader = self._default_excel_reader()
    if csv_reader is None:
        csv_reader = self._default_csv_reader()
    if tsv_reader is None:
        tsv_reader = csv_reader
    if docx_reader is None:
        docx_reader = self._default_docx_reader()
    self.pdf_reader = pdf_reader
    self.page_router = pdf_reader
    self.pdf = pdf_reader
    self.primary = pdf_reader
    self.primary_reader = pdf_reader
    self.text_reader = pdf_reader
    self.excel_reader = excel_reader
    self.excel = excel_reader
    self.xlsx_reader = excel_reader
    self.xls_reader = excel_reader
    self.spreadsheet_reader = excel_reader
    self.csv_reader = csv_reader
    self.csv = csv_reader
    self.delimited_reader = csv_reader
    self.tabular_reader = csv_reader
    self.tsv_reader = tsv_reader
    self.tsv = tsv_reader
    self.docx_reader = docx_reader
    self.docx = docx_reader
    self.word_reader = docx_reader
    self.word_document_reader = docx_reader
    self.readers = {}
    self.readers['pdf'] = self.pdf_reader
    self.readers['page_router'] = self.pdf_reader
    self.readers['excel'] = self.excel_reader
    self.readers['xlsx'] = self.excel_reader
    self.readers['xls'] = self.excel_reader
    self.readers['csv'] = self.csv_reader
    self.readers['tsv'] = self.tsv_reader
    self.readers['docx'] = self.docx_reader
    self.reader_registry = self.readers
    self.registry = self.readers
    self._reader_registry = self.readers
    self.registered = self.readers
    self.available_readers = self.readers
    self.registered_readers = self.readers
    self.readers.setdefault('pdfplumber', self.pdf_reader)
    self.readers.setdefault('pdf_plumber', self.pdf_reader)
    self.config = self._config
