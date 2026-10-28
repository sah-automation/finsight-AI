# Update Document Use Case

Application use case for validating and processing document updates.

**Belongs here:**
- Upload form validation for updates
- Duplicate detection
- New DocumentVersion creation
- Queueing ingestion with delta tracking
- Stamp update and cache invalidation
- Cascade/flagging of related documents
- Metrics recompute triggering (log/flag)

**Does not belong here:**
- Reader/vendor logic
- Storage or persistence internals beyond ports
