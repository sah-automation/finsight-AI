/**
 * Token parity harness (phase2 §5.2, issue #385).
 *
 * The prototype is the binding visual source: `prototype/styles.css` owns the
 * colour, type and spacing values. This test parses that stylesheet and the
 * app token source (`web/src/app/globals.css`) and fails when any value the
 * prototype declares differs in the app, when a token is missing, or when a
 * component hand-copies a raw value instead of using a token.
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';

import { describe, expect, it } from 'vitest';

/** Walk up from the working directory to the checkout that owns prototype/. */
function findRepoRoot(): string {
  let dir = process.cwd();
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dir, 'prototype', 'styles.css'))) return dir;
    dir = dirname(dir);
  }
  throw new Error('No checkout with prototype/styles.css found above the working directory');
}

const REPO_ROOT = findRepoRoot();
const PROTOTYPE_CSS = join(REPO_ROOT, 'prototype', 'styles.css');
const APP_CSS = join(REPO_ROOT, 'web', 'src', 'app', 'globals.css');
const APP_SRC = join(REPO_ROOT, 'web', 'src');

/** next/font declares `--font-inter` on <html>; every other token lives in globals.css. */
const RUNTIME_TOKENS = new Set(['--font-inter']);

/** Prototype-only chrome that §0 of UI_STANDARDS.md forbids shipping. */
const PROTOTYPE_ONLY_SELECTOR = '.pv';

type Declaration = { property: string; value: string };
type Rule = { selector: string; declarations: Declaration[] };

const prototypeCss = readFileSync(PROTOTYPE_CSS, 'utf8');
const appCss = readFileSync(APP_CSS, 'utf8');

function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

function findClosingBrace(source: string, open: number): number {
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    const char = source[i];
    if (char === '"' || char === "'") {
      i = skipString(source, i);
      continue;
    }
    if (char === '{') depth += 1;
    if (char === '}') {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  throw new Error(`Unbalanced braces at offset ${open}`);
}

function skipString(source: string, open: number): number {
  const quote = source[open];
  for (let i = open + 1; i < source.length; i += 1) {
    if (source[i] === '\\') {
      i += 1;
      continue;
    }
    if (source[i] === quote) return i;
  }
  return source.length;
}

function parseDeclarations(body: string): Declaration[] {
  const declarations: Declaration[] = [];
  for (const chunk of body.split(';')) {
    const text = chunk.trim();
    if (!text || text.startsWith('@')) continue;
    const colon = text.indexOf(':');
    if (colon === -1) continue;
    declarations.push({
      property: text.slice(0, colon).trim(),
      value: text
        .slice(colon + 1)
        .trim()
        .replace(/\s*!important$/i, ''),
    });
  }
  return declarations;
}

function parseRules(css: string): Rule[] {
  const source = stripComments(css);
  const rules: Rule[] = [];
  let prelude = '';
  let i = 0;
  while (i < source.length) {
    const char = source[i];
    if (char === '{') {
      const close = findClosingBrace(source, i);
      const selector = prelude.trim();
      const body = source.slice(i + 1, close);
      if (/^@(media|supports|layer|container)\b/.test(selector)) {
        for (const child of parseRules(body)) {
          rules.push({ selector: `${selector} ${child.selector}`, declarations: child.declarations });
        }
      } else {
        rules.push({ selector, declarations: parseDeclarations(body) });
      }
      i = close + 1;
      prelude = '';
      continue;
    }
    if (char === '}' || char === ';') {
      prelude = '';
      i += 1;
      continue;
    }
    prelude += char;
    i += 1;
  }
  return rules;
}

function customProperties(rules: Rule[], include: (selector: string) => boolean): Map<string, string> {
  const properties = new Map<string, string>();
  for (const rule of rules) {
    if (!include(rule.selector)) continue;
    for (const declaration of rule.declarations) {
      if (!declaration.property.startsWith('--')) continue;
      properties.set(declaration.property, declaration.value);
    }
  }
  return properties;
}

const isTokenSelector = (selector: string): boolean =>
  selector.includes(':root') || selector.startsWith('@theme');

const prototypeTokens = customProperties(parseRules(prototypeCss), (selector) =>
  selector.includes(':root'),
);
const appTokens = customProperties(parseRules(appCss), isTokenSelector);

const COLOUR = /^(#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})|(rgb|rgba|hsl|hsla)\([^)]*\))$/i;

function colourTokens(tokens: Map<string, string>): Map<string, string> {
  const colours = new Map<string, string>();
  for (const [name, value] of tokens) {
    if (COLOUR.test(value)) colours.set(name, value);
  }
  return colours;
}

const prototypeColours = colourTokens(prototypeTokens);
const appColours = colourTokens(appTokens);

function normaliseColour(value: string): string {
  const compact = value.toLowerCase().replace(/\s+/g, '');
  const digits = compact.match(/^#([0-9a-f]+)$/)?.[1];
  if (digits !== undefined) {
    return `#${digits.length === 3 ? digits.split('').map((d) => d + d).join('') : digits}`;
  }
  return compact.replace(/(^|[,/(])\./g, '$10.');
}

function normalise(value: string): string {
  return value.toLowerCase().replace(/\s+/g, '').replace(/(^|[,/(])\./g, '$10.');
}

function normaliseFont(value: string): string {
  return normalise(value).replace(/['"]/g, '').replace(/var\(--font-inter\)/g, 'inter');
}

/** Every colour literal the prototype paints with, normalised for comparison. */
const prototypeColourLiterals = new Set(
  [...prototypeCss.matchAll(/#[0-9a-f]{3,8}\b|(?:rgb|rgba|hsla?)\([^)]*\)/gi)].map((match) =>
    normaliseColour(match[0]),
  ),
);

/** Geometry tokens: the 4px grid, radii and elevation (UI_STANDARDS §4.3). */
const GEOMETRY = /^(--s\d+|--r-(sm|md)|--r-lg|--shadow-pop)$/;

type TypeToken = { size: number; lineHeight: number | null };

function prototypeTypeScale(css: string): { sizes: Set<number>; pairs: Set<string> } {
  const sizes = new Set<number>();
  const pairs = new Set<string>();
  const add = (selector: string, size: number, lineHeight: number | null): void => {
    if (selector.includes(PROTOTYPE_ONLY_SELECTOR)) return;
    sizes.add(size);
    if (lineHeight !== null) pairs.add(`${size}/${lineHeight}`);
  };
  for (const rule of parseRules(css)) {
    const fontSize = rule.declarations.find((d) => d.property === 'font-size')?.value;
    const lineHeight = rule.declarations.find((d) => d.property === 'line-height')?.value;
    const shorthand = rule.declarations.find((d) => d.property === 'font')?.value;
    if (fontSize) {
      const size = Number(fontSize.match(/^(\d+(?:\.\d+)?)px$/)?.[1]);
      const height = Number(lineHeight?.match(/^(\d+(?:\.\d+)?)px$/)?.[1]);
      if (size) add(rule.selector, size, Number.isNaN(height) ? null : height);
    } else if (shorthand && /\dpx/.test(shorthand)) {
      const match = shorthand.match(/(\d+(?:\.\d+)?)px(?:\/(\d+(?:\.\d+)?)px)?/);
      if (match) add(rule.selector, Number(match[1]), match[2] ? Number(match[2]) : null);
    }
  }
  return { sizes, pairs };
}

function appTypeScale(tokens: Map<string, string>): { tokens: Map<string, TypeToken>; font: string } {
  const typeTokens = new Map<string, TypeToken>();
  for (const [name, value] of tokens) {
    const size = value.match(/^(\d+(?:\.\d+)?)px$/);
    if (!name.startsWith('--text-') || name.endsWith('--line-height') || !size) continue;
    const line = tokens.get(`${name}--line-height`)?.match(/^(\d+(?:.\d+)?)px$/);
    typeTokens.set(name, { size: Number(size[1]), lineHeight: line ? Number(line[1]) : null });
  }
  return { tokens: typeTokens, font: tokens.get('--font') ?? '' };
}

const prototypeScale = prototypeTypeScale(prototypeCss);
const appScale = appTypeScale(appTokens);

function sourceFiles(dir: string): string[] {
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

describe('colour tokens', () => {
  it('declares every prototype colour token at the same value', () => {
    const missing: string[] = [];
    const changed: string[] = [];
    for (const [name, value] of prototypeColours) {
      const appValue = appColours.get(name);
      if (appValue === undefined) {
        missing.push(name);
      } else if (normaliseColour(appValue) !== normaliseColour(value)) {
        changed.push(`${name}: prototype ${value}, app ${appValue}`);
      }
    }
    expect(missing, 'colour tokens missing from web/src/app/globals.css').toEqual([]);
    expect(changed, 'colour tokens that differ from prototype/styles.css').toEqual([]);
  });

  it('declares no colour the prototype does not paint with', () => {
    const extra = [...appColours]
      .filter(([name]) => !prototypeColours.has(name))
      .filter(([, value]) => !prototypeColourLiterals.has(normaliseColour(value)))
      .map(([name, value]) => `${name}: ${value}`);
    expect(extra, 'app-only colour tokens must use a value the prototype hard-codes').toEqual(
      [],
    );
  });
});

describe('spacing, radius and elevation tokens', () => {
  it('mirrors the prototype geometry tokens value for value', () => {
    const prototypeGeometry = [...prototypeTokens].filter(([name]) => GEOMETRY.test(name));
    const missing: string[] = [];
    const changed: string[] = [];
    for (const [name, value] of prototypeGeometry) {
      const appValue = appTokens.get(name);
      if (appValue === undefined) {
        missing.push(name);
      } else if (normalise(appValue) !== normalise(value)) {
        changed.push(`${name}: prototype ${value}, app ${appValue}`);
      }
    }
    expect(missing, 'geometry tokens missing from web/src/app/globals.css').toEqual([]);
    expect(changed, 'geometry tokens that differ from prototype/styles.css').toEqual([]);
  });

  it('declares no spacing token the prototype does not define', () => {
    const prototypeNames = new Set(
      [...prototypeTokens].map(([name]) => name).filter((name) => GEOMETRY.test(name)),
    );
    const extra = [...appTokens]
      .map(([name]) => name)
      .filter((name) => GEOMETRY.test(name) && !prototypeNames.has(name));
    expect(extra, 'app-only geometry tokens are not in the prototype scale').toEqual([]);
  });
});

describe('type scale', () => {
  it('covers every font size the prototype uses', () => {
    const appSizes = new Set([...appScale.tokens.values()].map((token) => token.size));
    const missing = [...prototypeScale.sizes].filter((size) => !appSizes.has(size));
    expect(missing, 'font sizes used by prototype/styles.css with no app token').toEqual([]);
  });

  it('covers every size and line-height pair the prototype declares', () => {
    const appPairs = new Set(
      [...appScale.tokens.values()]
        .filter((token) => token.lineHeight !== null)
        .map((token) => `${token.size}/${token.lineHeight}`),
    );
    const missing = [...prototypeScale.pairs].filter((pair) => !appPairs.has(pair));
    expect(missing, 'size/line-height pairs from prototype/styles.css with no app token').toEqual(
      [],
    );
  });

  it('uses the prototype font stack', () => {
    expect(appScale.font, 'the --font token must match prototype/styles.css').not.toBe('');
    expect(normaliseFont(appScale.font)).toBe(normaliseFont(prototypeTokens.get('--font') ?? ''));
  });
});

describe('component sources', () => {
  const files = sourceFiles(APP_SRC);

  it('contain no hand-copied colour values', () => {
    const raw: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, 'utf8');
      for (const match of content.matchAll(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g)) {
        const digits = match[1];
        if (digits === undefined) continue;
        // Purely numeric 3-digit hashes read as fragment ids; real palette
        // colours always contain a letter or the full six/eight digits.
        if (digits.length === 3 && !/[a-fA-F]/.test(digits)) continue;
        raw.push(`${file.replace(APP_SRC, 'src')}: #${digits}`);
      }
      for (const match of content.matchAll(/\b(?:rgb|rgba|hsl|hsla)\([^)]*\)/g)) {
        raw.push(`${file.replace(APP_SRC, 'src')}: ${match[0]}`);
      }
    }
    expect(raw, 'components must take colour from tokens, never a literal').toEqual([]);
  });

  it('reference only tokens the app declares', () => {
    const undeclared: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, 'utf8');
      for (const match of content.matchAll(/var\((--[a-z0-9-]+)\)/g)) {
        const token = match[1];
        if (token === undefined) continue;
        if (appTokens.has(token) || RUNTIME_TOKENS.has(token)) continue;
        undeclared.push(`${file.replace(APP_SRC, 'src')}: ${token}`);
      }
    }
    expect(undeclared, 'every var(--token) must be declared in globals.css').toEqual([]);
  });
});
