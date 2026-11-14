## Parent

Part of #115

## What to build

Turn the documented file and function size checks into failing architecture tests (files over 300 lines, functions over 30 lines). Complete the full refactor first; the exception list may contain only legitimate, reviewed data/config modules, each with a reason, owner, and removal condition. Update the generated standards report.

## Acceptance criteria

- [ ] The architecture gate fails on an oversized file or function.
- [ ] Every exception is justified and listed with reason, owner, and removal condition.
- [ ] No oversized module is silently exempt.
- [ ] The standards report reflects the failing gate and current exceptions.
- [ ] Binding pre-flight followed; full architecture gate green.
