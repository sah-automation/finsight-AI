# Waiting Line Adapter

Short-lived waiting line around heavy Q&A work.

**Implements:** `WaitingLine` port

**Belongs here:**
- `WaitingLineAdapter` - ordering, concurrency caps, company fairness and timeout
- `BusyResult` - friendly result returned when a request waits too long
- Wait-time logging for every trace

**Config:** `scale.queue_priority`, `scale.queue_max_wait_seconds`, traffic concurrency cap.

**Does not belong here:**
- Business logic about what work to run
- Model or database calls (callers pass the work in)
- Long-lived ingestion queues (that's queue/)
