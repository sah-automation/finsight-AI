## Parent

Part of #115

## What to build

Split the oversized LLM gateway, embedding, rerank, and metering adapters and decorator stacks while preserving decorator order (tracing → metering → retry → provider), streaming, retry behavior, and price-derived usage records.

## Acceptance criteria

- [ ] Each module is under the documented size limits.
- [ ] Model-port and metering contract suites pass.
- [ ] Decorator order, streaming, retries, and usage rows remain tested.
- [ ] Binding pre-flight followed; gates green.
