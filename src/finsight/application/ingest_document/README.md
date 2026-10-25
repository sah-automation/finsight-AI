# Ingest Document Use Case

Document ingestion flow steps.

**Belongs here:**
- File validation
- Text/table extraction (via `DocumentReader` port)
- Chunking strategy
- Embedding generation
- Vector upsert
- Metadata persistence
- State transitions

**Flow:** Template method pattern - fixed order (stored, processing, committed), overridable extraction step.
