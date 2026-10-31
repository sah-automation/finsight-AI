"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

from typing import Any


async def _read(
    self: Any,
    company_id: Any,
    content: Any = None,
    *,
    file_path: Any = None,
    filename: Any = None,
    file_name: Any = None,
    content_type: Any = None,
    **kwargs: Any,
) -> Any:
    self._require_company_id(company_id)

    # Allow overrides to flow through kwargs.
    if filename is None:
        filename = kwargs.get('filename', kwargs.get('file_name'))
    if file_name is None:
        file_name = kwargs.get('file_name')
    if file_path is None:
        file_path = kwargs.get('file_path')
    if content_type is None:
        content_type = kwargs.get('content_type')

    source = self._resolve_source(
        content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
    )

    if self._is_empty_content(source):
        return self._empty_result()

    ext = self._extension(
        source,
        filename=filename,
        file_name=file_name,
        file_path=file_path,
        content_type=content_type,
    )

    if self._is_legacy_extension(ext):
        try:
            return self._read_xls(source)
        except ImportError:
            raise
        except Exception as exc:
            # Surface legacy-module expectations clearly.
            if 'xlrd' in str(exc).lower():
                raise
            # Fall back to a clear ImportError if xlrd is unavailable.
            try:
                import xlrd  # type: ignore[import-untyped]
            except Exception as import_exc:  # pragma: no cover - defensive
                raise ImportError('xlrd is required to read legacy .xls workbooks') from import_exc
            raise
    # Default to openpyxl (.xlsx and friends). If openpyxl cannot parse the
    # workbook, attempt xlrd for genuine legacy files before failing.
    try:
        return self._read_xlsx(source)
    except Exception as openpyxl_exc:
        # Any workbook openpyxl cannot parse may be a legacy .xls file.
        try:
            import xlrd  # noqa: F401
        except Exception as import_exc:
            raise ImportError('xlrd is required to read legacy .xls workbooks') from import_exc
        try:
            return self._read_xls(source)
        except Exception:
            raise openpyxl_exc from None
