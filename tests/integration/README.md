# Integration Tests

Real adapters against real services (LocalStack, test Aurora, etc.).

**Belongs here:**
- Full ingestion flow with real S3, Textract, Aurora
- Question flow with real LiteLLM, pgvector
- Cache read/write with real DynamoDB
- Queue enqueue/dequeue with real SQS
- Auth with real Cognito (or LocalStack)

**Rules:**
- Run in CI with LocalStack/test containers
- Clean up resources after each test
- Tag as `@integration` for selective runs
- Not run on every commit (slow)