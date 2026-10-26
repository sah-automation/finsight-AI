# Fixture Builder

Generates the anonymized sample documents in `tests/fixtures/documents/` and the
golden question set in `tests/golden/questions/`.

The point is that a number is written down once. The documents and the answer
key read the same reconciled model, so an answer cannot disagree with the page it
cites. Editing a generated file by hand breaks that guarantee.

```bash
uv run python scripts/fixture_builder           # rebuild everything and validate
uv run python scripts/fixture_builder --check   # fail if the committed copy is stale
uv run python scripts/fixture_builder --refresh # ignore the one-day SEC cache
```

A run builds the models, writes the documents and the manifest, writes the
questions, thresholds and then validates the questions against the documents it
just produced. It exits non-zero on any problem, so CI can gate on it.

## Where the numbers come from

| Layer | File | What it holds |
|---|---|---|
| Source | `source.py` | SEC XBRL company facts, a one-day cache, the tag map |
| Model | `model.py` | Reconciled statements for both companies, all identities asserted |
| Fixture data | `docdata.py` | Budget, ledger, bank statement, invoice, board minutes, regions |
| Documents | `documents.py` | One writer per file, page counts re-read from disk |
| Questions | `questions.py` | Expected values computed from the model |
| Validation | `validate.py` | Structure, coverage and citation checks |

Financial statements come from published SEC XBRL facts for two real issuers,
rebuilt under the placeholders `company-a` and `company-b`. Everything else is
invented here. All names, addresses, account numbers and signatures are
fictional; see `tests/fixtures/documents/README.md`.

EPS is derived as net income divided by the weighted-average share count, not
copied from the filing, so EPS, net income and the share count always tie on the
page.

### The SEC cache

`fetch_company_facts` keeps the raw JSON in a temporary directory for 24 hours.
That keeps repeated builds fast and deterministic while the published facts
cannot change. Pass `--refresh` to refetch.

The SEC facts API rejects requests with a descriptive `User-Agent`; it answers
only a browser-shaped one. `source.py` sends a browser-shaped `User-Agent` plus a
`From` header that identifies the project.

## What the validator enforces

- Ids match `<prefix>-NNN`, are unique, and the prefix matches the file.
- Every expected number has a parseable value, a known unit, a consistent
  currency, and its value appears in the answer prose.
- Every citation names a document in the manifest, a page that exists, and a
  table label recorded on that page. For born-digital PDFs the label must also
  appear in that page's extracted text, which catches a heading that drifted to
  the next page.
- Every document is cited by at least one question.
- The set has at least 100 questions, 20 numeric, 10 insufficient-data cases and
  one access-denied case, covers all four roles, all six reader types and both
  companies.
- `thresholds.yaml` records the 95% numeric-accuracy gate and the coverage
  floors, and the README states the gate.

## Adding a document

1. Add the data to `docdata.py` (computed totals, never typed twice).
2. Add a writer to `documents.py` returning a `GeneratedDocument` with its
   per-page section map.
3. Add it to `build_all`.
4. Add questions to the matching group in `questions.py`, citing the document,
   page and recorded table label.
5. Rebuild. The validator will tell you if a citation, number or coverage rule
   is wrong.

## Notes

- `reportlab` is a dev-only dependency, used only to render the PDFs.
- The scanned bank statement is two image-only pages inside a PDF with no text
  layer, so the reader must run OCR. Page 2 is deliberately degraded to exercise
  the low-confidence path. The invoice is a single PNG.
- Rendering is deterministic: the same model produces byte-identical files, so a
  rebuild does not create phantom diffs. PDF, DOCX and XLSX writers pin their
  creation timestamps, and `--check` compares the committed copies byte for byte.
