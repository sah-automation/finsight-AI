# Unit Tests

Fast tests with fakes for ports. Mirrors src/ folder by folder.

**Structure:**
```
tests/unit/
  core/
  domain/
    entities/
    value_objects/
    services/
    ports/        # fake implementations for contract tests
  application/
    ask_question/
    ingest_document/
    ...
  adapters/       # only testing adapter-specific logic, not ports
  entrypoints/
  composition/
```

**Rules:**
- No network calls
- Fake ports from `tests/unit/domain/ports/`
- Test business logic, not vendor behavior
- Deterministic
