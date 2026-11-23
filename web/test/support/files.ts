/**
 * Filesystem helpers for the web test harnesses: locating the checkout and
 * listing the application source files a scan must cover.
 */

import { existsSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';

/** Walk up from the working directory to the checkout that owns prototype/. */
export function findRepoRoot(): string {
  let dir = process.cwd();
  for (;;) {
    if (existsSync(join(dir, 'prototype', 'styles.css'))) return dir;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error('No checkout with prototype/styles.css found above the working directory');
}

/** Application sources: .ts/.tsx, excluding declarations, tests and generated code. */
export function sourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'generated') files.push(...sourceFiles(path));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) continue;
    if (/\.d\.ts$/.test(entry.name) || /\.test\.(ts|tsx)$/.test(entry.name)) continue;
    files.push(path);
  }
  return files;
}
