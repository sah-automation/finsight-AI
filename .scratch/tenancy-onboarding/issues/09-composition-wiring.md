# 09: Wire everything in composition root

**What to build:** Wire PartitionManager adapter, onboarding use case, repositories, and endpoints in the composition root. Ensure DI everywhere with no `new` in app/domain. Build pilot/standard sets per config.

**Blocked by:** 08: Add partition existence gate to upload path

**Status:** ready-for-agent

- [ ] Update composition root to wire all new components
- [ ] Ensure DI pattern followed (constructor injection)
- [ ] Wire with config-driven choices
- [ ] No direct instantiation in application/domain
