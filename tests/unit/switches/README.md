# Switch Path Tests

Tests that verify both ON and OFF paths for every config switch.

## Requirement

Per CODING_STANDARDS.md §1.7 and §14: **Both paths of every switch must exist and be tested.**

## Structure

Each switch gets its own test file:
- `test_reranker_switch.py` - `reranker_enabled`
- `test_backup_request_switch.py` - `backup_request_enabled`
- `test_parallel_retrieval_switch.py` - `parallel_retrieval_enabled`
- `test_citation_check_switch.py` - `per_sentence_citation_check`
- `test_textract_switch.py` - `async_textract_enabled`
- `test_ocr_fallback_switch.py` - `ocr_fallback_enabled`
- `test_answer_cache_switch.py` - `answer_cache_enabled`
- `test_role_cache_switch.py` - `role_cache_enabled`
- `test_tracing_switch.py` - `detailed_tracing_enabled`
- `test_metering_switch.py` - `usage_metering_enabled`

## Test Pattern

Each switch test file must implement:

```python
@pytest.mark.switch
def test_<switch>_on(self):
    """Test behavior when switch is ENABLED."""
    # Given: config with switch=True
    # When: feature is exercised
    # Then: enabled behavior occurs

@pytest.mark.switch
def test_<switch>_off(self):
    """Test behavior when switch is DISABLED."""
    # Given: config with switch=False
    # When: feature is exercised
    # Then: disabled behavior occurs (fallback/alternative path)
```

## Coverage Meta-Test

`test_switch_coverage.py` automatically verifies:
1. Every field in `SwitchesConfig` has a test file mapping
2. Each mapped test file exists

Run the meta-test:
```bash
pytest tests/unit/switches/test_switch_coverage.py -v
```

## Running All Switch Tests

```bash
# All switch tests
pytest tests/unit/switches -v -m switch

# Specific switch
pytest tests/unit/switches/test_reranker_switch.py -v
```
