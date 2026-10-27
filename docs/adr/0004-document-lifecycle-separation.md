# ADR-0004: Document lifecycle management is separate from upload

## Status

Accepted

## Context

The Phase 1 upload contract originally treated `delete` as an `upload_type`
alongside `new` and `update`. That mixed two different user actions in one
form: ingesting a document and changing its lifecycle state.

This is a poor UX and creates an avoidable foot-gun: a user can issue a
delete-style upload by mistake while trying to add or replace a file. It also
under-specifies retrieval behaviour, because "soft delete for
`deleted_retention_days`, then purge" could be read as leaving deleted chunks
searchable during the retention window. That would pollute Q&A responses
within the 30 days.

The repository already has a dedicated `application/delete_document` use case,
whose job is soft delete, cache clearing, delayed purge and audit retention.
That use case should be the single lifecycle path.

## Decision

- `upload_type` is a document ingestion concern only: `new` or `update`.
- `delete`, `restore` and permanent `purge` are document-management actions.
- They are exposed through dedicated document library and recycle-bin
  endpoints/UI, not through the upload form or the ingestion queue.
- Soft delete is transactional and takes effect immediately:
  the document and its chunks are excluded from retrieval, citations and the
  source viewer even though physical data is retained for
  `deleted_retention_days`.
- Restore reverses the soft delete and invalidates cached answers.
- Permanent purge removes chunks, vectors, metrics and cache entries after
  confirmation; the audit entry remains.
- Upload, update and document-library delete all bump the document stamp and
  invalidate affected cached answers.

## Consequences

- `documents.upload_types` becomes `[new, update]`. Config validation
  follows this.
- The upload endpoint no longer accepts `delete`.
- A document library/search surface and a recycle bin are required UI and API
  slices in Phase 1.
- Role matrix work is clearer: soft delete, restore and purge become distinct
  actions, rather than one `delete` entry attached to upload.
- Search, vector and source-viewer repos must filter out soft-deleted
  documents in every path and be contract-tested for that.
- This refines the HLD's upload form text; the HLD's lifecycle intent
  (soft delete, then purge, audit entry retained) is unchanged.
