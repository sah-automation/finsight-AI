/**
 * Minimal CSS block parser used by the token parity harness.
 *
 * It understands only what the two token sources use: comments, rule blocks,
 * at-rule containers (`@media`, `@supports`, `@layer`) and declarations with
 * or without `!important`. It is deliberately not a general CSS parser: it
 * throws on unbalanced braces rather than guessing.
 */

export type Declaration = { property: string; value: string };
export type Rule = { selector: string; declarations: Declaration[] };

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

export function parseRules(css: string): Rule[] {
  const source = css.replace(/\/\*[\s\S]*?\*\//g, '');
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
          rules.push({
            selector: `${selector} ${child.selector}`,
            declarations: child.declarations,
          });
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

/** Custom properties declared by the rules whose selector `include` accepts. */
export function customProperties(
  rules: Rule[],
  include: (selector: string) => boolean,
): Map<string, string> {
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
