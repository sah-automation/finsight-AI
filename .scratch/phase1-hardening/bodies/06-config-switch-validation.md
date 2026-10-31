## Parent

Part of #115

## What to build

Enforce the binding validation rules from the config-switch guide against the typed config: cross-section combinations, ranges, registration checks, protected paths, retention rules, model/reader lists, and both-path enforcement. Extend the switch meta-test so switches outside `SwitchesConfig` also require an ON and OFF test. Invalid configuration must stop startup with an actionable message.

## Acceptance criteria

- [ ] Every implemented rule has a reject test and an accept test.
- [ ] Invalid combinations stop startup; unknown, missing, or misspelled switches fail loudly.
- [ ] The switch meta-test covers switches in every typed section and rejects untested paths.
- [ ] No silent fallback or validation bypass remains.
- [ ] Binding pre-flight followed; config, architecture, and switch gates green.
