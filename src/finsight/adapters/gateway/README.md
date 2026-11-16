# Gateway Adapter

The gateway adapter wraps the in-process litellm chain for the model-gateway
Lambda function (issue #330). It provides a thin interface:

- `chat_completions(**kwargs)` → async iterator of litellm-shaped chunk dicts
- `embeddings(**kwargs)` → litellm-shaped embedding response dict

The FastAPI bridge (``finsight.entrypoints.gateway.app``) delegates to this
adapter, keeping the entrypoint free of direct litellm imports to satisfy the
architectural invariant that external clients live in adapters/composition.
