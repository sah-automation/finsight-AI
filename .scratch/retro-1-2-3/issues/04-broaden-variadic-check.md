# 04: Broaden variadic constructor check

**What to build:** The architecture test `test_constructor_invariant.py` currently flags only literal `**kwargs: Any` in `__init__` signatures. Extend the AST visitor to also flag any variadic parameter (`**<identifier>`, `*args`, `*<identifier>`) in `__init__` methods, since these are used to silently absorb unknown constructor arguments (e.g., `**_aliases`, `**rest`).

**Blocked by:** #215 (ticket 01) — (needs clean pre-commit gate to run)

**Status:** ready-for-agent

- [ ] AST visitor in `tests/architecture/test_constructor_invariant.py` detects `**<any-name>` in `__init__`
- [ ] AST visitor detects `*args` / `*<any-name>` in `__init__`
- [ ] Test fails on current `steps/*.py` constructors that use `**_aliases` or `*args, **_ignored`
- [ ] Existing `BARE_KWARGS_CONSTRUCTOR_EXCEPTIONS` mechanism still works for reviewed exceptions
- [ ] No false positives on non-`__init__` methods
