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
