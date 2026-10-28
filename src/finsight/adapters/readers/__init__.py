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
    'PageRouter',
    'PdfPlumberReader',
    'TSVDocumentReader',
    'TSVReader',
    'TabularReader',
    'Tesseract',
    'TesseractReader',
    'Textract',
    'TextractReader',
    'TsvDocumentReader',
    'TsvReader',
]
