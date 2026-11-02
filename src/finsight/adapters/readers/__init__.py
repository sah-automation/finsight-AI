"""Document readers and routing helpers."""

from __future__ import annotations

from .base_reader import BaseReader

# Canonical adapter modules.
from .csv_reader import (
    CSV,
    Csv,
    CSVDocumentReader,
    CsvDocumentReader,
    CSVReader,
    CsvReader,
    DelimitedDocumentReader,
    DelimitedReader,
    TabularReader,
    TSVDocumentReader,
    TsvDocumentReader,
    TSVReader,
    TsvReader,
)
from .docx_reader import (
    DOCX,
    Docx,
    DocxDocumentReader,
    DocxReader,
)
from .excel_reader import Excel, ExcelReader
from .format_reader_selector import (
    FormatReader,
    FormatReaderSelector,
    FormatSelector,
    ReaderFactorySelector,
    ReaderSelector,
)
from .page_router import PageRouter
from .pdf_plumber_reader import *  # noqa: F403
from .pdf_plumber_reader import PdfPlumberReader
from .pdfplumber import *  # noqa: F403
from .self_hosted_layout_reader import (
    Layout,
    LayoutDocumentReader,
    LayoutReader,
    SelfHosted,
    SelfHostedDocumentReader,
    SelfHostedLayout,
    SelfHostedLayoutReader,
    SelfHostedReader,
)
from .table_reader import (
    LayoutTableReader,
    Table,
    TableDocumentReader,
    TableLayoutReader,
    TableReader,
)
from .tesseract_reader import Tesseract, TesseractReader
from .textract_reader import Textract, TextractReader

# Retained public spellings.
from .xls import *  # noqa: F403
from .xlsx import *  # noqa: F403

__all__ = [
    'CSV',
    'DOCX',
    'BaseReader',
    'CSVDocumentReader',
    'CSVReader',
    'Csv',
    'CsvDocumentReader',
    'CsvReader',
    'DelimitedDocumentReader',
    'DelimitedReader',
    'Docx',
    'DocxDocumentReader',
    'DocxReader',
    'Excel',
    'ExcelReader',
    'FormatReader',
    'FormatReaderSelector',
    'FormatSelector',
    'Layout',
    'LayoutDocumentReader',
    'LayoutReader',
    'LayoutTableReader',
    'PageRouter',
    'PdfPlumberReader',
    'ReaderFactorySelector',
    'ReaderSelector',
    'SelfHosted',
    'SelfHostedDocumentReader',
    'SelfHostedLayout',
    'SelfHostedLayoutReader',
    'SelfHostedReader',
    'TSVDocumentReader',
    'TSVReader',
    'Table',
    'TableDocumentReader',
    'TableLayoutReader',
    'TableReader',
    'TabularReader',
    'Tesseract',
    'TesseractReader',
    'Textract',
    'TextractReader',
    'TsvDocumentReader',
    'TsvReader',
]

# Decorator wrappers for extraction paid calls.
from .metered_extraction import *  # noqa: F403
from .retrying_extraction import *  # noqa: F403
from .traced_extraction import *  # noqa: F403
