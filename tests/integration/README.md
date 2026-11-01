# Integration Tests

Real adapters against real services (LocalStack, test Aurora, etc.).

**Belongs here:**
- Full ingestion flow with real S3, Textract, Aurora
- Question flow with real LiteLLM, pgvector
- Cache read/write with real DynamoDB
- Queue enqueue/dequeue with real SQS
- Auth with real Cognito (or LocalStack)

**Status:** the migration round-trip integration test
(`test_migration_roundtrip.py`) is landed (issue #141) and runs against a real
PostgreSQL instance. Adapter end-to-end flows remain pending the first real
adapter integration test (issue #74). The suite fails rather than passes when it
has no non-skipped tests.

**Rules:**
- Run in CI with LocalStack/test containers
- Clean up resources after each test
- Tag as `@integration` for selective runs
- Not run on every commit (slow)

## Real sample document ingestion (issue #143 / H28)

Sample documents by supported format (all present in
``tests/fixtures/documents/`` and listed in ``manifest.yaml``):

| Format | Example | Reader path exercised |
|---|---|---|
| PDF (born digital) | ``pdf__company-a__2025-FY__annual-report.pdf`` | ``PdfPlumberReader`` |
| PDF (scanned) | ``scan__company-a__2026-Q3__bank-statement.pdf`` | ``PageRouter`` + ``TesseractReader`` (OCR) |
| Excel | ``xlsx__company-a__2025-FY__budget-vs-actual.xlsx`` | ``ExcelReader`` |
| CSV / TSV | ``csv__company-a__2025-FY__q4-ledger.csv`` | ``CsvReader`` |
| DOCX | ``docx__company-a__2025-FY__board-notes.docx`` | ``DocxReader`` |
| Image (PNG) | ``image__company-a__2025-FY__vendor-invoice.png`` | ``TesseractReader`` (OCR) |


The anonymized sample documents in ``tests/fixtures/documents/`` (see that
folder's ``README.md`` and ``manifest.yaml``) cover all five supported input
formats: born-digital PDF, scanned PDF (OCR, including one low-confidence page),
Excel (``.xlsx``), semicolon-delimited CSV, and DOCX.  Reader-level
verification of these documents runs through the unit/switch suites and the
reader contract suites; no database or object storage is required.

The **staging-only** portions of the acceptance criteria are:

- End-to-end ingestion of the sample documents through the full pipeline (S3
  upload, virus scan, OCR via Textract/Tesseract, Aurora persistence, vector
  writes, metric extraction).  This requires LocalStack/the test Aurora stack
  and is exercised by integration tests tagged ``@integration``.
- The golden question set against the real ask flow on the ``standard``
  (staging) configuration.  The unit-testable harness lives in
  ``tests/golden``; the live (non-deterministic) variant is governed by the
  ``golden-live`` workflow (``.github/workflows/golden-live.yml``).

The golden score baselines in ``tests/golden/baselines/`` remain the release
gate: a drop against ``numeric_accuracy`` (>= 0.95) or ``citation_accuracy``
(>= 1.0) blocks the release, enforced by ``compare_to_baseline`` and the
``golden-tests`` CI job.
