# Sample Documents

Anonymized documents used by reader contract tests, ingestion tests and the golden set.

Add the files here and list each one in `manifest.yaml`.

**Required coverage**

| Kind | At least | What it must exercise |
|---|---|---|
| PDF, born digital | 2 | Multi-page text, headings, at least one table |
| PDF, scanned | 1 | OCR path (`scan_reader`) and a low-confidence page |
| Image scan | 1 | OCR path for a single page |
| Excel (`.xlsx` / `.xls`) | 1 | Multiple sheets, headers and units |
| CSV / TSV | 1 | Header row and a non-comma delimiter if possible |
| DOCX | 1 | Paragraphs, lists and a table |

**Naming**

```
<kind>__<company>__<period>__<description>.<ext>
```

Examples:

- `pdf__company-a__2025-Q3__income-statement.pdf`
- `scan__company-a__2025-Q3__bank-statement.pdf`
- `xlsx__company-a__2025-Q3__budget-vs-actual.xlsx`
- `csv__company-a__2025-09__ledger.csv`
- `docx__company-a__2025-Q3__board-notes.docx`

Use `company-a`, `company-b` and similar placeholders, never a real company name.

**Anonymization checklist**

- Replace names, emails, phone numbers, addresses, account numbers, tax IDs and signatures.
- Keep the numbers realistic and internally consistent; the golden set depends on them.
- Keep the page count, tables, headers and units realistic.
- Confirm no hidden customer data remains in document properties, comments or sheet names.
- Run `detect-secrets` before committing.

**Size**

- Each file under 500 KB, whole folder under 5 MB. The pre-commit
  `check-added-large-files` hook enforces the 500 KB per-file limit.
- If a file legitimately needs to be larger, stop and ask before adding it.

**Generated files**

The current contents are produced by `uv run python scripts/fixture_builder`.
Do not edit them by hand: change the generator and rebuild, or the manifest, the
questions and the documents will drift apart. The generator also validates the
question set against the documents it just wrote.
