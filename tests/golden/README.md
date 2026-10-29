# Golden Tests

The 100+ canonical question set for regression testing.

**Belongs here:**
- `questions/` - question set, one YAML file per category (format in its `README.md`)
- `run_golden.py` - runner for pilot and standard config
- `compare_results.py` - diff and score calculation

**Scoring harness:** `run_golden.py` runs the shared question set on pilot
and standard configurations; `compare_results.py` computes citation and
numeric accuracy. Issue #77.

**Rules:**
- Runs on both pilot and standard config
- Same answers expected on both (or documented differences)
- At least 95% numeric accuracy; a score drop blocks release
- Every answer must carry a verifiable citation unless the expected result is "insufficient data"
- Coverage includes numbers, citations, insufficient data, access and every reader type
- Each question is tagged: category, difficulty, role and expected sources

**Does not belong here:**
- Unit or integration tests
- One-off exploratory questions
- Questions that cannot be verified from a sample document in `tests/fixtures/documents/`
