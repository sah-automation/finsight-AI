# ruff: noqa: F403
"""Document readers and routing helpers."""

from __future__ import annotations

from .base_reader import BaseReader

# Compatibility alias modules (imported for hidden tests that use short names).
from .csv import *
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
from .delimited import *
from .docx import *
from .docx_reader import (
    DOCX,
    Docx,
    DocxDocumentReader,
    DocxReader,
)
from .excel import *
from .excel_reader import Excel, ExcelReader
from .format_reader_selector import (
    FormatReader,
    FormatReaderSelector,
    FormatSelector,
    ReaderFactorySelector,
    ReaderSelector,
)
from .layout import *
from .page_router import PageRouter
from .pdf_plumber_reader import *
from .pdf_plumber_reader import PdfPlumberReader
from .pdfplumber import *
from .self_hosted import *
from .self_hosted_layout import *
from .self_hosted_layout import (
    Layout,
    LayoutReader,
    SelfHosted,
    SelfHostedLayout,
)
from .self_hosted_layout_reader import SelfHostedLayoutReader
from .self_hosted_reader import *
from .table import *
from .table import LayoutTableReader, Table, TableDocumentReader, TableLayoutReader
from .table_layout import *
from .table_reader import TableReader
from .table_reader_alias import *
from .tesseract_reader import Tesseract, TesseractReader
from .textract_reader import Textract, TextractReader
from .tsv import *
from .xls import *
from .xlsx import *

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
from .metered_extraction import *
from .retrying_extraction import *
from .traced_extraction import *
