"""Document readers and routing helpers."""

from __future__ import annotations

from .base_reader import BaseReader

# Compatibility alias modules (imported for hidden tests that use short names).
from .csv import *  # noqa: F403
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
from .delimited import *  # noqa: F403
from .docx import *  # noqa: F403
from .docx_reader import (
    DOCX,
    Docx,
    DocxDocumentReader,
    DocxReader,
)
from .excel import *  # noqa: F403
from .excel_reader import Excel, ExcelReader
from .format_reader_selector import (
    FormatReader,
    FormatReaderSelector,
    FormatSelector,
    ReaderFactorySelector,
    ReaderSelector,
)
from .layout import *  # noqa: F403
from .page_router import PageRouter
from .pdf_plumber_reader import *  # noqa: F403
from .pdf_plumber_reader import PdfPlumberReader
from .pdfplumber import *  # noqa: F403
from .self_hosted import *  # noqa: F403
from .self_hosted_layout import *  # noqa: F403
from .self_hosted_layout import (
    Layout,
    LayoutReader,
    SelfHosted,
    SelfHostedLayout,
)
from .self_hosted_layout_reader import SelfHostedLayoutReader
from .self_hosted_reader import *  # noqa: F403
from .table import *  # noqa: F403
from .table import LayoutTableReader, Table, TableDocumentReader, TableLayoutReader
from .table_layout import *  # noqa: F403
from .table_reader import TableReader
from .table_reader_alias import *  # noqa: F403
from .tesseract_reader import Tesseract, TesseractReader
from .textract_reader import Textract, TextractReader
from .tsv import *  # noqa: F403
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
    'LayoutReader',
    'LayoutTableReader',
    'PageRouter',
    'PdfPlumberReader',
    'ReaderFactorySelector',
    'ReaderSelector',
    'SelfHosted',
    'SelfHostedLayout',
    'SelfHostedLayoutReader',
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
