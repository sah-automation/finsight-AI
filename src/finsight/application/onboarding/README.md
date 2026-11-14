# Onboarding application

Orchestrates creation of a company tenant: validates inputs, allocates a
company id, resolves region/cell, creates the company record, creates partitions
and indexes via the partition manager, initializes identity/cache/audit, and
marks the company ready only after the final commit. Idempotent via request_key.

Does not import adapters; depends only on domain ports.
