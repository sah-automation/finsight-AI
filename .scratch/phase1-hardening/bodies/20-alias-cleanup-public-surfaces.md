## Parent

Part of #115

## What to build

Clean up alias-module sprawl. Inventory compatibility shims, choose one canonical module per concept, add intentional `__all__` exports, migrate imports, and remove aliases. Any alias retained for compatibility must document the reason and the removal condition. Run as expand → migrate imports → contract so every batch stays green.

## Acceptance criteria

- [ ] A reviewed alias inventory is committed with canonical module choices.
- [ ] Each concept has one obvious import location; undocumented shims are removed.
- [ ] Retained aliases document reason and removal condition.
- [ ] Package initializers expose intentional public surfaces only.
- [ ] Import contracts and tests remain green.
- [ ] Binding pre-flight followed; gates green.
