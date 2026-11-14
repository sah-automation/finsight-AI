# ADR-0005: Full LLM content capture on trace spans is an opt-in exception to the no-content logging rule

## Status

Accepted

## Context

`CODING_STANDARDS.md` section 11 says: never log question text, chunk text,
answers or personal data; log ids and sizes only. Section 17 repeats it as
"no sensitive data in logs". Those rules were written when the only telemetry
surface was application logging (stdout and structured log records).

The observability epic (#273) needs a different surface for development and
eval work: review the full prompt sent to the LLM and the full response
received, inspect the embedding input chunks to judge chunking quality, and
see the rerank query and candidate texts to debug which documents get cited.
Without a documented exception, every tracer implementation would have to
guess what is allowed, and reviewers would read any prompt/response capture as
a section 11 violation.

A second constraint already exists in code: a redaction blocklist that strips
sensitive fields from span attributes. It was added as the safety net for the
tracing decorators and must keep working whether or not content capture is on.

## Decision

Section 11 continues to govern **application logging** unchanged: stdout and
structured log records carry ids, sizes and metrics only, and the log-side
redaction (`core/logging/redaction.py`) stays as it is. Nothing in the logging
path changes.

**Trace spans** are a separate surface and get one exception. A new switch,
`llm_content_capture_enabled`, gates full content capture on spans:

- When the switch is on, the traced decorators attach content to span
  attributes under GenAI semantic-convention attribute names:
  `gen_ai.prompt.messages` and `gen_ai.completion.messages` for LLM calls
  (`TracedLLM`), `gen_ai.embedding.texts` for embedding calls
  (`TracedEmbedding`), and `gen_ai.rerank.query` / `gen_ai.rerank.candidates`
  for rerank calls (`TracedReranker`).
- When the switch is off, none of these attributes are emitted. Both paths are
  contract-tested against every `TracingPort` implementation.
- Defaults: on for dev and test, off for staging and production. Changing an
  environment follows the config switch guide (one switch change per release,
  by pull request), so production capture is always a deliberate opt-in.
- The redaction blocklist applies **always, including when capture is on**.
  Sensitive names (`question`, `chunk`, `answer`, `pii`, `credential`,
  `signed_url`, `secret`, `token`, `password`, `prompt`, `raw_text`,
  `document_text`, `api_key`, `email`, `phone`, `address`, `ssn`,
  `credit_card`, `authorization`), URL-shaped values and PII-shaped values are
  removed from span attributes, including nested inside captured content.
  LLM token-count and latency metric keys are explicitly allow-listed because
  their names contain sensitive substrings while their values are aggregates.
- Company identity on spans stays hashed (ADR-0007): captured content is never
  attached to a raw tenant identifier.

## Consequences

- Full prompt/response review and embedding/rerank inspection work in dev and
  test by default, which unblocks prompt review and eval work.
- Production content capture happens only after an explicit config PR, and
  turns off again the same way.
- Every tracing adapter implementation must enforce the redaction blocklist or
  fail the shared contract tests; new captured fields must be checked against
  the blocklist before they are emitted.
- Captured content grows span size; keeping the switch off in staging and
  production keeps export volume and cost predictable (see ADR-0006).
- Section 11's text stays as it is: reviewers treat content capture on spans as
  the documented exception recorded here, not as a rule change.
