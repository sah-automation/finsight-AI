## Parent

Part of #115

## What to build

Remove deprecated `asyncio.get_event_loop` access from library, adapter, and entrypoint code. Use explicit async execution or one documented compatibility helper; do not mix sync and async behavior inside one class. Add a regression test that prevents the deprecated pattern from returning.

## Acceptance criteria

- [ ] No deprecated event-loop access remains in source code.
- [ ] Async paths run cleanly on Python 3.12+ without deprecation warnings.
- [ ] A regression test fails if the deprecated pattern returns.
- [ ] No class mixes sync and async behavior.
- [ ] Binding pre-flight followed; gates green.
