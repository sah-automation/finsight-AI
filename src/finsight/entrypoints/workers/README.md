# Worker Entrypoints

SQS and Step Functions message handlers.

**Belongs here:**
- Ingestion job handler
- Reprocessing job handler
- Report generation handler
- Forecast refresh handler

**Each handler:**
1. Parses message payload
2. Gets use case from composition
3. Calls use case with job context
4. Handles retries (decorator)
5. Acknowledges or dead-letters

**Rule:** Every job is safe to repeat (idempotent via job_id + upsert)

**Does not belong here:**
- Business logic
- Direct adapter calls
- Config reading