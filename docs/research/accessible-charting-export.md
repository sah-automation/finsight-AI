# Research: Accessible Charting and Client-Side Export for Next.js 15 App Router

**Issue:** #347 — Research accessible charting and client-side export for Next.js
**Date:** November 18, 2026
**Branch:** `research/accessible-charting-export`

---

## Executive Summary

This report evaluates charting libraries for a Next.js 15 App Router codebase with requirements for:
- WCAG 2.2 AA compliance (keyboard navigation, screen reader support, colour-blind safe palettes, focus management, table fallback)
- Client-side PNG/PDF export from chart data (not screenshots), carrying metadata (currency, units, period, source list, Draft/Estimated/Updating labels)
- Bundle size efficiency and tree-shaking
- TypeScript support and SSR compatibility
- Future headless/Node rendering capability for server-side export
- Accessibility testing approach (axe-core, vitest-axe)

**Top Recommendation: Recharts v3 (with accessibilityLayer enabled) + Tremor for pre-styled components**
- Best balance of accessibility, React-native API, TypeScript support, and ecosystem maturity
- Tremor builds on Recharts with Tailwind/shadcn/ui aesthetics and dark mode out of the box
- Nivo is the alternative if Canvas rendering for 50K+ points or exotic chart types (Sankey, Heatmap, Choropleth) are needed
- Chart.js via react-chartjs-2 only if Canvas performance for massive datasets is critical and accessibility can be custom-built
- Visx only if maximum customization is required and team has D3 expertise

---

## 1. Chart Library Options — WCAG 2.2 AA Compliance Comparison

### 1.1 Recharts v3 (Released December 2024)

| WCAG 2.2 AA Criterion | Support | Notes |
|---|---|---|
| **2.1.1 Keyboard** | ✅ Full | Arrow-key navigation between data points; `Tab` enters/exits chart container; `accessibilityLayer` prop (default `true` in v3) enables keyboard controls |
| **2.4.7 Focus Visible** | ✅ | Focus indicators on data points via CSS; customizable via `activeDot`, `activeShape` props |
| **2.4.11 Focus Not Obscured (Minimum)** | ⚠️ Partial | Requires careful CSS z-index management for tooltips/legends |
| **1.3.1 Info & Relationships** | ✅ | ARIA roles (`role="img"`, `role="application"`), `aria-label` on chart container, `aria-live` region for tooltip announcements |
| **1.4.3 Contrast (Minimum)** | ⚠️ Developer responsibility | Default colours may not meet 4.5:1; must use colour-blind safe palettes (see §1.5) |
| **1.4.11 Non-text Contrast** | ⚠️ Developer responsibility | Grid lines, axis ticks, data point borders need ≥3:1 |
| **Table Fallback** | ✅ Manual | Data already in JS array — render `<table>` alongside chart with same data |

**Key accessibility features in v3:**
- `accessibilityLayer` prop (default `true`) injects ARIA labels, roles, keyboard controls
- `useChart` hook exposes scales/data for custom accessible tooltips
- Screen reader support: JAWS/NVDA auto-enter Forms Mode via `role="application"`; VoiceOver requires QuickNav off (document for users)
- Tooltip content announced via `aria-live="polite"` region

**Gaps requiring developer action:**
- Colour-blind safe palettes not built-in (must supply)
- Table fallback must be implemented separately
- Focus management for complex composed charts needs testing
- No built-in "data table" toggle component

### 1.2 Tremor (v3+, built on Recharts)

| WCAG 2.2 AA Criterion | Support | Notes |
|---|---|---|
| **2.1.1 Keyboard** | ✅ | Inherits Recharts `accessibilityLayer` |
| **2.4.7 Focus Visible** | ✅ | Tailwind focus-ring utilities applied by default |
| **1.3.1 Info & Relationships** | ✅ | ARIA labels on chart wrappers; semantic HTML structure |
| **1.4.3 Contrast** | ✅ Better defaults | Tailwind slate/gray palette meets 4.5:1 in light/dark modes |
| **Colour-blind palettes** | ⚠️ Manual | Uses Recharts colours; can pass `colors` prop with safe palette |
| **Dark mode** | ✅ Built-in | `dark:` Tailwind variants automatic |

**Advantage:** Pre-styled, accessible defaults matching shadcn/ui aesthetic. Dark mode works without configuration. Less customization surface than raw Recharts.

### 1.3 Nivo (@nivo/line, @nivo/bar, etc.)

| WCAG 2.2 AA Criterion | Support | Notes |
|---|---|---|
| **2.1.1 Keyboard** | ✅ Excellent | Built-in keyboard navigation for all chart types; arrow keys traverse data points |
| **2.4.7 Focus Visible** | ✅ | Focus styles on data points, legend items, axis ticks |
| **1.3.1 Info & Relationships** | ✅ Excellent | Comprehensive ARIA: `role="img"`, `aria-labelledby`, `aria-describedby`, data point `role="button"` with `aria-label` |
| **1.4.3 Contrast** | ✅ Theming system | Built-in colour-blind safe palettes (`colorblind`, `nivo` categories) |
| **Table fallback** | ✅ HTML render mode | `@nivo/bar/html` renders as positioned `<div>` elements — fully accessible to screen readers without SVG |
| **Reduced motion** | ✅ | Respects `prefers-reduced-motion` |

**Standout:** Only library in this comparison with **WCAG 2.1 AA out of the box** per documentation. HTML render mode (`@nivo/*/html`) provides maximum accessibility — each bar/point is a focusable `<div>` with ARIA labels.

### 1.4 Chart.js via react-chartjs-2

| WCAG 2.2 AA Criterion | Support | Notes |
|---|---|---|
| **2.1.1 Keyboard** | ❌ Minimal | Canvas is single focusable element; no built-in data point navigation. Microsoft Fluent wrapper adds arrow-key tooltip navigation but not upstream |
| **2.4.7 Focus Visible** | ⚠️ Canvas only | Only canvas element receives focus |
| **1.3.1 Info & Relationships** | ❌ None | Canvas is opaque to screen readers; requires manual `aria-label` + fallback table |
| **1.4.3 Contrast** | ⚠️ Developer responsibility | All colours developer-defined |
| **Table fallback** | ✅ Manual | Data available for separate table |

**Verdict:** **Not recommended** for accessibility-first projects. Canvas architecture fundamentally limits screen reader access. Only viable if you build a custom accessibility layer (as Microsoft did for Teams) — significant engineering investment.

### 1.5 Visx (@visx/*)

| WCAG 2.2 AA Criterion | Support | Notes |
|---|---|---|
| **2.1.1 Keyboard** | ❌ None built-in | Low-level primitives; keyboard navigation must be implemented from scratch |
| **2.4.7 Focus Visible** | ❌ None built-in | Developer responsibility |
| **1.3.1 Info & Relationships** | ❌ None built-in | SVG output but no ARIA unless manually added |
| **1.4.3 Contrast** | ❌ Developer responsibility | Complete control, complete responsibility |
| **Table fallback** | ✅ Manual | Data available |

**Verdict:** Maximum flexibility, **zero built-in accessibility**. Team must implement all WCAG requirements. Only suitable if you have dedicated accessibility expertise and need visualizations no library provides (e.g., custom trading charts, scientific visualizations).

### 1.6 Colour-Blind Safe Palettes — Recommendations

| Library | Built-in Palettes | Recommended Approach |
|---|---|---|
| Recharts/Tremor | None | Use `colors` prop with [ColorBrewer](https://colorbrewer2.org/) qualitative sets (e.g., `Set2`, `Paired`) or [Paul Tol's palettes](https://personal.sron.nl/~pault/) |
| Nivo | ✅ `colorblind`, `nivo` categories | Use `colors={{ scheme: 'colorblind' }}` prop |
| Chart.js | None | Manual configuration with safe palettes |
| Visx | None | Manual with D3-scale-chromatic (`d3-scale-chromatic` package) |

**Recommended safe palette for financial charts (8 colours, CVD-safe):**
```typescript
const FINANCIAL_PALETTE = [
  '#0072B2', // Blue
  '#D55E00', // Vermillion
  '#009E73', // Bluish green
  '#CC79A7', // Reddish purple
  '#E69F00', // Orange
  '#56B4E9', // Sky blue
  '#F0E442', // Yellow
  '#000000', // Black (high contrast fallback)
];
```

---

## 2. Client-Side PNG/PDF Export from Data (Not Screenshots)

### 2.1 Core Principle: Export SVG → Canvas → PNG/PDF

All SVG-based libraries (Recharts, Tremor, Nivo SVG, Visx) render to `<svg>` in the DOM. The export pipeline:

```
1. Get SVG string from rendered chart (via ref + XMLSerializer)
2. Convert SVG → Canvas using canvg
3. Canvas → PNG via canvas.toDataURL('image/png')
4. PNG → PDF via react-pdf / jsPDF / pdf-lib
```

### 2.2 Recharts/Tremor Export Implementation

```typescript
// utils/chartExport.ts
import { saveAs } from 'file-saver';
import { Canvg } from 'canvg';
import { Document, Page, Image, View, Text, StyleSheet } from '@react-pdf/renderer';

interface ChartMetadata {
  currency: string;
  units: string;
  period: string;
  sources: string[];
  status: 'Draft' | 'Estimated' | 'Updating' | 'Final';
  title: string;
}

// Step 1: Extract SVG from Recharts ref
export function getChartSVG(chartRef: React.RefObject<HTMLDivElement>): string {
  const container = chartRef.current;
  if (!container) throw new Error('Chart ref not attached');
  const svg = container.querySelector('svg');
  if (!svg) throw new Error('No SVG found in chart');
  return new XMLSerializer().serializeToString(svg);
}

// Step 2: SVG → PNG (client-side, no screenshot)
export async function svgToPng(svgString: string, width: number, height: number): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = width * 2; // 2x for retina
  canvas.height = height * 2;
  const ctx = canvas.getContext('2d')!;
  ctx.scale(2, 2);

  const v = await Canvg.fromString(ctx, svgString, {
    ignoreMouse: true,
    ignoreAnimation: true,
  });
  await v.render();

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob!), 'image/png', 1.0);
  });
}

// Step 3: PNG → PDF with metadata
export async function generateChartPDF(
  pngBlob: Blob,
  metadata: ChartMetadata
): Promise<Blob> {
  const pngDataUrl = URL.createObjectURL(pngBlob);

  const doc = (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>{metadata.title}</Text>
          <Text style={styles.status}>{metadata.status}</Text>
        </View>
        <Image src={pngDataUrl} style={styles.chartImage} />
        <View style={styles.metadata}>
          <Text>Currency: {metadata.currency}</Text>
          <Text>Units: {metadata.units}</Text>
          <Text>Period: {metadata.period}</Text>
          <Text>Sources: {metadata.sources.join(', ')}</Text>
        </View>
      </Page>
    </Document>
  );

  const pdfBlob = await doc.toBlob();
  URL.revokeObjectURL(pngDataUrl);
  return pdfBlob;
}

// Usage in component
export function useChartExport(chartRef: React.RefObject<HTMLDivElement>) {
  const exportPNG = async () => {
    const svg = getChartSVG(chartRef);
    const { width, height } = chartRef.current!.querySelector('svg')!.getBoundingClientRect();
    const png = await svgToPng(svg, width, height);
    saveAs(png, 'chart.png');
  };

  const exportPDF = async (metadata: ChartMetadata) => {
    const svg = getChartSVG(chartRef);
    const { width, height } = chartRef.current!.querySelector('svg')!.getBoundingClientRect();
    const png = await svgToPng(svg, width, height);
    const pdf = await generateChartPDF(png, metadata);
    saveAs(pdf, 'chart.pdf');
  };

  return { exportPNG, exportPDF };
}
```

**Dependencies:** `canvg`, `file-saver`, `@react-pdf/renderer` (or `jspdf`/`pdf-lib`)

### 2.3 Nivo Export Advantage

Nivo provides `getSvg()` on responsive components and has a built-in HTML render mode that can be serialized directly:

```tsx
import { ResponsiveLine } from '@nivo/line';

function ChartWithExport() {
  const chartRef = useRef<ResponsiveLine>(null);

  const exportSVG = () => {
    // Nivo exposes SVG via ref
    const svg = chartRef.current?.getSvg();
    // ... same pipeline
  };
}
```

### 2.4 Chart.js Export (Canvas-native)

```typescript
// Chart.js renders to <canvas> directly
const canvas = chartRef.current?.canvas;
const pngBlob = await new Promise<Blob>((resolve) =>
  canvas.toBlob((b) => resolve(b!), 'image/png')
);
// Same PDF pipeline
```

**Advantage:** No SVG→Canvas conversion needed. **Disadvantage:** No vector output (SVG), accessibility gaps.

### 2.5 Metadata Injection Requirements

| Metadata Field | Source | Injection Point |
|---|---|---|
| `currency` | Chart data config | PDF footer / PNG EXIF (optional) |
| `units` | Axis config | PDF footer |
| `period` | Data range | PDF footer |
| `sources` | Data provenance | PDF footer |
| `status` (Draft/Estimated/Updating) | Business logic | PDF header + watermark |

**Recommendation:** Create a `ChartMetadata` interface in shared types. Pass to export utility. Render as PDF footer + optional semi-transparent watermark on PNG.

---

## 3. Bundle Size Impact and Tree-Shaking

| Library | Bundle Size (gzipped) | Tree-Shaking | Notes |
|---|---|---|---|
| **Recharts v3** | ~50 KB | ⚠️ Limited | Single package; imports pull most of library. v3 improved but still ~150 KB raw. |
| **Tremor** | ~70 KB | ⚠️ Limited | Bundles Recharts + components. Only 6 chart types. |
| **Nivo** | 30–80 KB per chart | ✅ Excellent | Modular: `@nivo/line`, `@nivo/bar` separate. Pay only for what you use. |
| **Chart.js + react-chartjs-2** | ~65 KB | ✅ Good | Must register only needed components: `ChartJS.register(CategoryScale, LineElement, ...)` |
| **Visx** | ~5–15 KB per primitive | ✅ Excellent | Import only `@visx/shape`, `@visx/scale`, `@visx/axis`, etc. |

### 3.1 Practical Bundle Analysis

```bash
# Analyze your actual bundle
npx @next/bundle-analyzer
# or
ANALYZE=true npm run build
```

**Key findings from pkgpulse (March 2026):**
- Recharts: 2.4M weekly downloads, ~370 KB raw, ~50 KB gzipped
- Tremor: ~250K weekly, ~200 KB raw (includes Recharts)
- Nivo: ~380K weekly, modular — `@nivo/line` ~40 KB core + D3 deps
- Chart.js: ~4.1M weekly (mostly non-React), ~65 KB gzipped

### 3.2 Tree-Shaking Best Practices

```typescript
// Recharts - import specific components (helps slightly)
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Nivo - import per chart type (excellent tree-shaking)
import { ResponsiveLine } from '@nivo/line'; // Only line chart code

// Chart.js - register only what you use (critical)
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

// Visx - import primitives (best granularity)
import { LinePath } from '@visx/shape';
import { scaleLinear, scaleBand } from '@visx/scale';
import { AxisBottom, AxisLeft } from '@visx/axis';
```

---

## 4. TypeScript Support and SSR Compatibility (Next.js 15 App Router)

### 4.1 TypeScript Support Matrix

| Library | Types Included | Quality | Custom Tooltip Typing | Generic Data Support |
|---|---|---|---|---|
| **Recharts v3** | ✅ Built-in | Excellent | Requires `TooltipProps<ValueType, NameType>` | Good — `dataKey` string typing |
| **Tremor** | ✅ Built-in | Excellent | Simplified props, less flexible | Good — `index`, `categories` string typing |
| **Nivo** | ✅ Built-in | Excellent | Fully typed theme + data props | Excellent — discriminated unions for data formats |
| **Chart.js** | ✅ Built-in (v3+) | Good | `ChartOptions<'line'>` generics | Good — dataset typing via generics |
| **Visx** | ✅ Built-in | **Best** | `useTooltip<DatumType>` preserves datum | **Best** — D3 scale types flow through |

**Visx wins on TypeScript depth** due to D3-first design — scale types (`ScaleLinear<number, number>`) propagate through components. Nivo close second. Recharts/Tremor adequate for standard dashboards.

### 4.2 Next.js 15 App Router SSR Compatibility

| Library | Server Component | Client Component Required | Hydration Issues | Notes |
|---|---|---|---|---|
| **Recharts v3** | ❌ | ✅ `"use client"` | ⚠️ SSR regression in 3.x (see §5) | SVG renders on server but interactive features need client |
| **Tremor** | ❌ | ✅ `"use client"` | ⚠️ Same as Recharts | All components marked `"use client"` in package |
| **Nivo** | ❌ | ✅ `"use client"` | ❌ **Broken** — `MotionConfigProvider` uses Context | Maintainer: "won't fix" for Next.js App Router SSR (§5) |
| **Chart.js** | ❌ | ✅ `"use client"` | ✅ Works | Canvas renders client-only; SSR returns empty `<canvas>` |
| **Visx** | ❌ | ✅ `"use client"` | ✅ Works | Pure React SVG components; SSR via `renderToString` works |

**Critical Finding:** **None of these libraries work as React Server Components (RSC).** All require `"use client"` because they use:
- React Context (Nivo, Recharts `ResponsiveContainer`)
- Browser APIs (`ResizeObserver`, `window`, `document`)
- Client-side lifecycle (`useEffect`, `useLayoutEffect`)

**Pattern for Next.js 15 App Router:**
```tsx
// app/dashboard/charts/RevenueChart.tsx
'use client';

import { LineChart } from 'recharts';
import dynamic from 'next/dynamic';

// For heavy charts, defer client bundle
const HeavyChart = dynamic(() => import('./HeavyChart'), {
  ssr: false, // or true if SSR works
  loading: () => <ChartSkeleton />,
});

export function RevenueChart({ data }: { data: DataPoint[] }) {
  return <LineChart data={data} ... />;
}
```

**Server-side data fetching pattern:**
```tsx
// app/dashboard/page.tsx (Server Component)
import { getRevenueData } from '@/lib/data';
import { RevenueChart } from './charts/RevenueChart';

export default async function DashboardPage() {
  const data = await getRevenueData(); // Server-side fetch
  return <RevenueChart data={data} />; // Pass to Client Component
}
```

---

## 5. Headless/Node Rendering for Future Server-Side Export

### 5.1 Current State (Not Phase 2 Scope)

| Library | `renderToString` Support | Node Canvas Export | Notes |
|---|---|---|---|
| **Recharts 2.x** | ✅ Worked | Via canvg | Full SVG output |
| **Recharts 3.x** | ❌ **Broken** | ❌ | Regression: outputs ~100 chars vs 5KB in 2.x. Maintainer: "client-side library, SSR never explicitly supported" — but 2.x worked. Issue #6139 / #5997 open. |
| **Tremor** | ❌ | ❌ | Inherits Recharts 3.x regression |
| **Nivo** | ❌ | ❌ | Context-based architecture prevents SSR; maintainer closed #2626 as "not planned" |
| **Chart.js** | ⚠️ Empty canvas | ✅ Via `chartjs-node-canvas` | `chartjs-node-canvas` uses `node-canvas` polyfill — works well for server PNG/PDF |
| **Visx** | ✅ Works | ✅ Via canvg | Pure React SVG components; `renderToString` produces valid SVG |

### 5.2 Recommended Path for Future Server-Side Export

**Option A: Chart.js + chartjs-node-canvas (Most Mature)**
```typescript
// server/chartExport.ts
import { ChartJSNodeCanvas } from 'chartjs-node-canvas';

const chartJSNodeCanvas = new ChartJSNodeCanvas({ width: 800, height: 400 });

export async function renderChartToBuffer(config: ChartConfiguration): Promise<Buffer> {
  return chartJSNodeCanvas.renderToBuffer(config);
}
```
- **Pros:** Actively maintained, used in production, supports all Chart.js chart types
- **Cons:** Different API from client (configuration-based), Canvas not SVG

**Option B: Visx + renderToString + canvg (Best SVG Fidelity)**
```typescript
// server/chartExport.ts
import { renderToString } from 'react-dom/server';
import { VisxChart } from '@/charts/VisxChart';
import { Canvg } from 'canvg';

export async function renderVisxChartToPng(data: DataPoint[]): Promise<Buffer> {
  const svgString = renderToString(<VisxChart data={data} width={800} height={400} />);
  const canvas = createCanvas(800, 400);
  const ctx = canvas.getContext('2d');
  const v = await Canvg.fromString(ctx, svgString);
  await v.render();
  return canvas.toBuffer('image/png');
}
```
- **Pros:** Identical rendering to client (same components), SVG vector intermediate
- **Cons:** Requires Visx investment, more code to maintain

**Option C: Playwright / Puppeteer (Highest Fidelity, Heaviest)**
- Spin up headless browser, navigate to chart page, screenshot
- **Use only if** pixel-perfect match required and other options fail

**Phase 2 Recommendation:** **Do not implement server-side export now.** Document the Visx + `renderToString` path as the future direction if server-side PDF generation becomes required. Client-side export (§2) covers Phase 2 needs.

---

## 6. Accessibility Testing Approach

### 6.1 Tooling Stack

| Tool | Purpose | Installation |
|---|---|---|
| **axe-core** | Core accessibility engine (WCAG 2.1/2.2 rules) | `npm i -D axe-core` |
| **vitest-axe** | Vitest matcher for axe-core | `npm i -D vitest-axe` |
| **@axe-core/playwright** | E2E accessibility in real browser | `npm i -D @axe-core/playwright` |
| **eslint-plugin-jsx-a11y** | Lint-time accessibility rules | `npm i -D eslint-plugin-jsx-a11y` |
| **react-axe** | Dev console violations during development | `npm i -D react-axe` |

### 6.2 Unit/Component Testing with vitest-axe

```typescript
// vitest.setup.ts
import { expect } from 'vitest';
import * as matchers from 'vitest-axe/matchers';
expect.extend(matchers);

// chart.a11y.test.tsx
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { LineChart } from '@/components/charts/LineChart';
import { ResponsiveContainer } from 'recharts';

describe('LineChart accessibility', () => {
  const data = [
    { month: 'Jan', revenue: 4000 },
    { month: 'Feb', revenue: 3000 },
    { month: 'Mar', revenue: 6000 },
  ];

  it('has no axe violations', async () => {
    const { container } = render(
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} />
      </ResponsiveContainer>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('exposes chart as img role with accessible name', () => {
    render(
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} aria-label="Monthly revenue 2024" />
      </ResponsiveContainer>
    );
    const chart = screen.getByRole('img', { name: /monthly revenue 2024/i });
    expect(chart).toBeInTheDocument();
  });

  it('supports keyboard navigation to data points', async () => {
    const { container } = render(
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} accessibilityLayer />
      </ResponsiveContainer>
    );
    const chart = container.querySelector('[role="application"]');
    expect(chart).toBeInTheDocument();

    // Test keyboard interaction via userEvent
    const user = userEvent.setup();
    await user.tab(); // Focus chart container
    await user.keyboard('{ArrowRight}'); // Navigate to first data point
    // Assert tooltip announced via aria-live
  });
});
```

### 6.3 E2E Testing with Playwright + axe

```typescript
// e2e/chart-accessibility.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('dashboard charts have no accessibility violations', async ({ page }) => {
  await page.goto('/dashboard');

  // Wait for charts to hydrate
  await page.waitForSelector('[role="img"]');

  const accessibilityScanResults = await new AxeBuilder({ page })
    .include('[role="img"]') // Scope to charts
    .analyze();

  expect(accessibilityScanResults.violations).toHaveLength(0);
});

test('chart keyboard navigation works', async ({ page }) => {
  await page.goto('/dashboard');
  const chart = page.locator('[role="application"]').first();

  await chart.focus();
  await page.keyboard.press('ArrowRight');

  // Verify tooltip announced (aria-live region)
  const tooltip = page.locator('[role="tooltip"]');
  await expect(tooltip).toBeVisible();
});
```

### 6.4 CI Integration

```yaml
# .github/workflows/a11y.yml
name: Accessibility Tests
on: [push, pull_request]
jobs:
  a11y-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm run test:a11y

  a11y-e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm run build
      - run: npm run start &
      - run: npx playwright install --with-deps chromium
      - run: npm run test:a11y:e2e
```

```json
// package.json scripts
{
  "scripts": {
    "test:a11y": "vitest run --reporter=verbose src/**/*.a11y.test.tsx",
    "test:a11y:e2e": "playwright test e2e/chart-accessibility.spec.ts"
  }
}
```

### 6.5 Manual Testing Checklist (Per Release)

- [ ] **Keyboard only:** Tab to chart, arrow keys navigate data points, Escape exits
- [ ] **Screen reader (NVDA/JAWS/VoiceOver):** Chart announced as "image" or "application", data points readable, tooltip content spoken
- [ ] **Colour contrast:** All text ≥4.5:1, UI elements ≥3:1 (use axe + browser devtools)
- [ ] **Colour-blind simulation:** Test with Chrome DevTools "Emulate vision deficiencies" (Protanopia, Deuteranopia, Tritanopia)
- [ ] **Zoom 200%:** Chart remains usable, no horizontal scrolling at 320px width
- [ ] **Reduced motion:** Animations disabled, transitions respect `prefers-reduced-motion`
- [ ] **Table fallback:** Data table present and accurate for each chart

---

## 7. Detailed Recommendation Matrix

### 7.1 For FinSight-AI Phase 2 (Next.js 15 App Router, SaaS Dashboard)

| Requirement | Recommended Choice | Rationale |
|---|---|---|
| **Primary chart library** | **Recharts v3 + Tremor** | Best React integration, Tremor gives shadcn/ui aesthetic + dark mode free, accessibilityLayer in v3 covers WCAG basics |
| **Accessibility baseline** | Recharts `accessibilityLayer={true}` + custom colour-blind palette + table fallback component | Meets WCAG 2.2 AA with developer effort on colours/table |
| **Client export (PNG/PDF)** | SVG → canvg → canvas → PNG → react-pdf | Uses same SVG data as render, injects metadata |
| **Bundle size** | Acceptable (~70 KB gzipped for Tremor) | Dashboard not bundle-critical; code-split with `dynamic()` |
| **TypeScript** | Excellent | Both libraries ship types |
| **SSR** | `"use client"` on chart components, data fetched in Server Components | Standard Next.js 15 pattern |
| **Future server export** | Document Visx path; not implemented in Phase 2 | Visx + `renderToString` gives identical SVG |

### 7.2 Alternative: Nivo (If Requirements Change)

**Switch to Nivo if:**
- Need Canvas rendering for 50K+ data points (financial tick data)
- Need exotic chart types (Sankey, Heatmap, Choropleth, Calendar)
- Want HTML render mode for maximum accessibility without custom work
- Can accept `"use client"` and no true SSR

**Trade-offs:** Larger bundle per chart type, no SSR in App Router, steeper learning curve for customization.

### 7.3 Not Recommended for Phase 2

| Library | Reason |
|---|---|
| **Chart.js** | Canvas architecture blocks screen reader access; accessibility layer requires custom engineering |
| **Visx** | Zero built-in accessibility; requires D3 expertise; high development cost for standard dashboards |

---

## 8. Implementation Checklist for Phase 2

### 8.1 Chart Component Architecture

- [ ] Create `ChartWrapper` client component with `"use client"` handling ResponsiveContainer + accessibilityLayer
- [ ] Build `AccessibleLineChart`, `AccessibleBarChart`, `AccessibleDonutChart` on Recharts/Tremor
- [ ] Implement `ColourBlindPaletteProvider` context with `FINANCIAL_PALETTE`
- [ ] Create `ChartTableFallback` component rendering `<table>` from same data
- [ ] Add `ChartMetadata` interface to shared types (`@finsight/types`)

### 8.2 Export Pipeline

- [ ] Add `canvg`, `file-saver`, `@react-pdf/renderer` to dependencies
- [ ] Implement `useChartExport` hook (§2.2)
- [ ] Add export buttons (PNG/PDF) to chart toolbar
- [ ] Test metadata injection (currency, units, period, sources, status)

### 8.3 Accessibility

- [ ] Enable `accessibilityLayer={true}` on all charts
- [ ] Add `aria-label` prop to all chart components (required)
- [ ] Configure Tailwind focus-ring for chart focus states
- [ ] Document VoiceOver QuickNav limitation in user-facing help

### 8.4 Testing

- [ ] Add `vitest-axe` + `axe-core` to devDependencies
- [ ] Write `.a11y.test.tsx` for each chart component
- [ ] Add Playwright + `@axe-core/playwright` for E2E
- [ ] Configure CI workflow for accessibility tests

### 8.5 Documentation

- [ ] Add chart accessibility guide to `docs/accessibility/charts.md`
- [ ] Document export pipeline and metadata schema
- [ ] Record ADR for chart library choice

---

## 9. References

1. **Recharts Accessibility Wiki** — https://github.com/recharts/recharts/wiki/Recharts-and-accessibility
2. **Recharts v3 Release Notes** — https://recharts.org/en-US/blog/2024-12-01-v3-release
3. **Tremor Documentation** — https://tremor.so/docs
4. **Nivo Accessibility** — https://nivo.rocks/guides/accessibility
5. **Chart.js Accessibility** — https://www.chartjs.org/docs/latest/general/accessibility.html
6. **Visx Accessibility Issue** — https://github.com/airbnb/visx/issues/12
7. **pkgpulse: Recharts vs Chart.js vs Nivo vs Visx 2026** — https://www.pkgpulse.com/guides/recharts-vs-chartjs-vs-nivo-vs-visx-react-charting-2026
8. **pkgpulse: Recharts v3 vs Tremor vs Nivo 2026** — https://www.pkgpulse.com/guides/recharts-v3-vs-tremor-vs-nivo-react-charting-2026
9. **Recharts SSR Regression #6139** — https://github.com/recharts/recharts/issues/6139
10. **Nivo Next.js SSR #2626** — https://github.com/plouc/nivo/issues/2626
11. **axe-core** — https://github.com/dequelabs/axe-core
12. **vitest-axe** — https://github.com/chaance/vitest-axe
13. **canvg** — https://github.com/canvg/canvg
14. **chartjs-node-canvas** — https://www.npmjs.com/package/chartjs-node-canvas
15. **react-pdf** — https://react-pdf.org/
16. **WCAG 2.2 Specification** — https://www.w3.org/TR/WCAG22/
17. **Highcharts Accessibility Module** (reference implementation) — https://www.highcharts.com/docs/accessibility/accessibility-module

---

## Appendix A: Colour-Blind Safe Palette Validation

```typescript
// Test palette contrast ratios
const palette = [
  '#0072B2', '#D55E00', '#009E73', '#CC79A7',
  '#E69F00', '#56B4E9', '#F0E442', '#000000',
];

// All pairs should be distinguishable under:
// - Protanopia (red-blind)
// - Deuteranopia (green-blind)
// - Tritanopia (blue-blind)
// Use https://davidmathlogic.com/colorblind/ to validate
```

---

## Appendix B: Recharts 3.x SSR Regression Details

| Version | `renderToString` Output | Contains `<svg>` |
|---|---|---|
| 2.15.4 | ~5,186 chars | ✅ Yes |
| 3.0.0 | ~121 chars | ❌ No |
| 3.0.2 | ~121 chars | ❌ No |
| 3.1.0 | ~102 chars | ❌ No |

**Workaround for Phase 2:** Use `"use client"` on chart components; accept client-only rendering. Server-rendered HTML will show empty container until hydration. For SEO-critical charts, consider static SVG generation at build time via separate script.

---

*End of Report*
