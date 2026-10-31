## Parent

Part of #115

## What to build

Split the oversized API entrypoints into thin handlers that delegate to application use cases. Preserve authentication/authorization, request validation, error mapping, streaming, and the published OpenAPI contract.

## Acceptance criteria

- [ ] Each entrypoint module is under the documented size limits.
- [ ] Handlers contain no business logic.
- [ ] API/OpenAPI tests and authorization behavior remain unchanged.
- [ ] Binding pre-flight followed; gates green.
