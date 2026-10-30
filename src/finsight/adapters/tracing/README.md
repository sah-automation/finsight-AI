# Tracing Adapter

Tracing and span emission adapter implementing `TracingPort`.

**Implements:** `TracingPort` (start_span)

**Belongs here:**
- `TracingAdapter` - structured spans for active/disabled tracing modes
- Company identifier conversion to non-sensitive trace attributes
- Redaction of sensitive span attributes
- Minimal spans in disabled mode

**Does not belong here:**
- Business logic
- Redaction policy primitives (those are in domain/core)
