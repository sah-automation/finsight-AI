"""TableReader adapter for table-sensitive pages."""

from __future__ import annotations

from typing import Any


def _resolve_underlying(self: Any) -> Any:
    if self._delegate is not None:
        return self._delegate
    name = self._delegate_name or self._config_table_reader_name()
    if name is None:
        name = 'pdfplumber'
    name_low = str(name).strip().lower()
    cls: Any = None
    module_path: str | None = None
    attr: str | None = None
    if name_low in ('pdfplumber', 'pdf_plumber', 'pdf', 'pdfplumber_reader'):
        module_path = 'finsight.adapters.readers.pdf_plumber_reader'
        attr = 'PdfPlumberReader'
    elif 'textract' in name_low:
        module_path = 'finsight.adapters.readers.textract_reader'
        attr = 'TextractReader'
    elif (
        'layout' in name_low
        or 'self_hosted' in name_low
        or 'self-hosted' in name_low
        or 'table' in name_low
    ):
        module_path = 'finsight.adapters.readers.self_hosted_layout_reader'
        attr = 'SelfHostedLayoutReader'
    else:
        module_path = 'finsight.adapters.readers.pdf_plumber_reader'
        attr = 'PdfPlumberReader'

    try:
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, attr, None)
    except Exception:
        cls = None
    if cls is None:
        try:
            import finsight.adapters.readers as pkg

            alias_map = {
                'PdfPlumberReader': ('PdfPlumberReader', 'PdfPlumber'),
                'TextractReader': ('TextractReader', 'Textract'),
                'SelfHostedLayoutReader': (
                    'SelfHostedLayoutReader',
                    'SelfHostedLayout',
                    'LayoutReader',
                    'Layout',
                ),
            }
            for alias in alias_map.get(attr, (attr,)):
                cls = getattr(pkg, alias, None)
                if cls is not None:
                    break
        except Exception:
            cls = None
    if cls is None:
        return None
    try:
        return cls(config=self._config, session=self._session)
    except Exception:
        try:
            return cls()
        except Exception:
            return None
