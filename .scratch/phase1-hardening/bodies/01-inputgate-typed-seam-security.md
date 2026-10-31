## Parent

Part of #115

## What to build

Give the InputGate an explicit typed configuration dependency and a single documented check entry point. Remove positional/command-object guessing and undocumented aliases while preserving configurable PII actions and prompt-injection detection. Replace the skipped prompt-injection placeholder with executable tests at the InputGate seam covering direct and obfuscated injection, benign lookalikes, PII mask/block/log, length limits, and blocked-path errors.

## Acceptance criteria

- [ ] InputGate accepts a typed config dependency and rejects undocumented positional/alias construction.
- [ ] One documented check entry point is used by all callers and the result contract is explicit.
- [ ] The skipped prompt-injection placeholder is removed; no placeholder-only security suite remains.
- [ ] Tests cover injection allow/block, PII mask/block/log, length limits, and blocked-path error behavior.
- [ ] Both configured actions (block and allow) are exercised independently.
- [ ] Binding pre-flight followed; `make typecheck && make lint && pytest tests/architecture tests/unit tests/security -q` is green.
