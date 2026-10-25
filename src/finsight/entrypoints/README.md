# Entrypoints

Thin doors into the app. No business logic here.

**Dependency rule:** Entrypoints import `application` and get objects from `composition`.

**Belongs here:**
- API handlers (FastAPI routes)
- Worker handlers (SQS, Step Functions)
- Scheduled job handlers

**Does not belong here:**
- Any business logic
- Direct port usage (use application use cases)
- Config reading
- Database connections