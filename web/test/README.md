# web/test

Test-only helpers for the web application.

- `*.test.ts` / `*.test.tsx` files here are collected by Vitest (see `web/vitest.config.ts`).
- `support/` holds non-test helper modules the harnesses import: CSS parsing
  (`css.ts`), checkout/source-file location (`files.ts`) and other fixture code
  that has no assertions of its own. Nothing else belongs here.
- `stubs/` holds module stubs wired through Vitest aliases (for example
  `server-only`, which only makes sense inside the Next.js runtime).
- `setup.ts` is the single Vitest setup file; test-specific setup goes in the
  test file that needs it.

Business behaviour is tested next to the code it exercises, under `web/src`.
