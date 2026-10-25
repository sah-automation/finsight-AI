# Document Readers

File format readers implementing `DocumentReader` port.

**Implements:** `DocumentReader` port

**Belongs here:**
- `PdfPlumberReader` - PDF text/tables
- `TesseractReader` - OCR for scanned PDFs
- `TextractReader` - AWS Textract (async)
- `ExcelReader` - spreadsheets
- `CsvReader` - CSV files
- `DocxReader` - Word documents

**Factory:** `ReaderFactory.create(config)` - registry-based

**Contract:** Every reader returns same shape: text, tables, page numbers

**Does not belong here:**
- Chunking (domain/services)
- File download (that's storage/)
- Business logic about which reader to use