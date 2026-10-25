# Queue Adapter

SQS message queue.

**Implements:** `QueuePort` (enqueue, dequeue, ack, nack, dead-letter)

**Belongs here:**
- `SqsQueue` - boto3 wrapper
- Message serialization (JSON)
- Visibility timeout handling
- Dead-letter queue routing
- Batch operations

**Does not belong here:**
- Job payload definitions (those are in application/)
- Worker logic (that's entrypoints/workers/)
- Business logic about job priority
