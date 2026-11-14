# Reprocess Use Case

Application use case for rolling document reprocessing.

**Belongs here:**
- Rolling/lower-priority reprocessing of a few companies at a time
- Idempotent scheduling and execution
- No mixing of old and new chunks/vectors
- Staying on current done version until atomic commit
- Audit and fan-out for affected documents

**Does not belong here:**
- Reader/vendor logic
- Storage or persistence internals beyond ports
