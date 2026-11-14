# Messaging Adapter

Publishes document lifecycle events and cascade signals after a version changes.

**Implements:** `ChangeEventPublisher`

**Belongs here:**
- `ChangeEventPublisher` - fan-out of `DocumentChangeEvent` values
- Optional transport/sink wiring (SQS, EventBridge, an in-process bus)
- Cascade request signals for dependent documents

**Does not belong here:**
- Deciding which documents are affected (that is application logic)
- Cache invalidation itself (the cache adapter listens to these events)
- Business rules about version states
