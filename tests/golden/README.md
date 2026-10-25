# Golden Tests

The 100+ canonical question set for regression testing.

**Belongs here:**
- `questions.yaml` - question, expected answer, citations, metadata
- `run_golden.py` - runner for pilot and standard config
- `compare_results.py` - diff and score calculation

**Rules:**
- Runs on both pilot and standard config
- Same answers expected on both (or documented differences)
- Score drop blocks release
- Questions cover: metrics, forecasting, risk, decisions, citations
- Each question tagged: category, difficulty, expected_sources

**Does not belong here:**
- Unit or integration tests
- One-off exploratory questions
