# Contract Tests

One shared test per port, run against every adapter implementation.

**Purpose:** Prove Liskov Substitution - any adapter can replace another.

**Structure:**
```
tests/contract/
  test_llm_gateway.py        # run against LiteLLMGateway, MockGateway
  test_vector_search.py      # run against AuroraPgVectorSearch, MockSearch
  test_document_reader.py    # run against PdfPlumber, Tesseract, Textract...
  test_cache_port.py         # run against DynamoAnswerCache, MockCache
  ...
```

**Each test file:**
- Defines abstract test class with port test cases
- Concrete test classes inherit and provide adapter fixture
- Tests: happy path, error cases, edge cases, idempotency

**Rules:**
- Every new adapter must pass all contract tests for its port
- Contract tests live here, not in adapter folders
- Run in CI for every adapter
