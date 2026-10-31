## Parent

Part of #115

## What to build

Add a CI or architecture check that every paid call site (LLM, embedding, rerank, extraction/OCR) is wrapped by the metering decorator or records an equivalent usage row. Fix any unmetered site. Use a test double to prove a paid call produces one usage row with company, service, model, units, cost, and trace identifier.

## Acceptance criteria

- [ ] The paid-call inventory is checked automatically.
- [ ] An unmetered paid call fails the gate.
- [ ] A test double proves the required usage-row fields.
- [ ] Metering failures remain non-fatal to the user answer.
- [ ] Binding pre-flight followed; gates green.
