# Golden Question Set

The 100+ canonical questions used to score Phase 1. This folder holds the questions only; the runner and scorer are built later.

Add one YAML file per category, for example `revenue.yaml`, `margins.yaml`, `citations.yaml`, `insufficient_data.yaml`, `access.yaml`. Start from `_template.yaml`.

**Coverage rules**

- At least 100 questions in total.
- At least 20 numeric questions with an exact expected value, currency and unit.
- At least 10 "insufficient data" cases: missing period, missing document, weak evidence and cross-company questions.
- At least one question per supported reader type: PDF, scanned PDF, image scan, Excel, CSV and DOCX.
- At least a few questions per role, including an access-denied case.
- Every expected citation points to a document in `tests/fixtures/documents/manifest.yaml`, with page and table where applicable.

**Scoring rules**

- Numeric accuracy must be at least 95%. A drop blocks the release.
- A wrong citation fails the question even if the answer text looks right.
- An answer without a citation is a failure, unless the expected result is "insufficient data".
- The same set runs on pilot and standard config. Document any expected difference.

**Authoring rules**

- `id` is permanent. Never renumber or reuse an id; add a new one.
- Questions must be answerable from the sample documents, not from general knowledge.
- Keep the wording realistic; include some messy, real-user phrasing.
- No real personal or customer data anywhere in a question, answer or note.
- Keep each question in exactly one file.

**Does not belong here**

- Unit or integration tests
- Exploratory or one-off questions
- Questions whose answer is not verifiable from a sample document
