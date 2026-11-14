# Test Fixtures

Input files used by contract, ingestion and integration tests.

**Belongs here:**
- `documents/` - anonymized sample documents for every supported file type
- Small, deterministic files that a test can process without network access

**Rules:**
- Anonymize everything. No real names, emails, addresses, account numbers, tax IDs or customer data.
- Keep each file under 5 MB and the whole folder under 50 MB. Use Git LFS if a file must be larger.
- Record every document in `documents/manifest.yaml` so tests can find it by type and feature.
- Do not put model outputs, generated embeddings or database dumps here.
- Fixtures are test data, not production documents. Never point a real environment at this folder.
