# Model Gateway Entrypoint

This directory contains the FastAPI bridge that runs behind the AWS Lambda Web
Adapter. It exposes a thin HTTP surface over the in-process litellm chain for
the remote `llm_transport` (issue #330):

- `POST /v1/chat/completions` — streams litellm-shaped NDJSON chunks
- `POST /v1/embeddings` — returns litellm-shaped embedding response
- `GET /healthz` — readiness probe for the Web Adapter

The bridge itself is a pure shell: it normalizes request/response JSON and
enforces the optional shared key check, but all litellm calls are delegated to
the `ModelGatewayAdapter` in `src/finsight/adapters/gateway/`. This keeps the
architectural invariant that external clients (boto3, httpx, litellm) are only
constructed in adapters or composition.
