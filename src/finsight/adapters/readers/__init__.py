"""Document readers and routing helpers."""

from __future__ import annotations

from .base_reader import BaseReader
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
from .page_router import PageRouter
from .pdf_plumber_reader import PdfPlumberReader
from .self_hosted_layout import (
    Layout,
    LayoutReader,
    SelfHosted,
    SelfHostedLayout,
)
from .self_hosted_layout_reader import SelfHostedLayoutReader
from .table import LayoutTableReader, Table, TableDocumentReader, TableLayoutReader
from .table_reader import TableReader
from .tesseract_reader import Tesseract, TesseractReader
from .textract_reader import Textract, TextractReader

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
    'Layout',
    'LayoutReader',
    'LayoutTableReader',
    'PageRouter',
    'PdfPlumberReader',
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
