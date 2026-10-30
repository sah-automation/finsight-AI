# FinSight AI: UI Standards

For the coding agent and every developer building the frontend. Read this before writing any UI code. If a task clashes with this file, `CODING_STANDARDS.md` or the parent plan, stop and ask. Do not quietly break a rule.

Related files: `finsightAI.md`, `finsight_config_switches.md`, `finsight_known_risks.md`, `phase1_mvp_plan.md`, `CODING_STANDARDS.md`.

Scope: Phase 1 screens are fully specified (section 6). Later phase screens (dashboards, forecasts, alerts, approvals) have design direction only (section 7). Do not build them early.

---

## 1. Design direction (what we are copying and why)

We studied products that finance and research teams already trust. We take one lesson from each. We do not copy their branding.

| Reference | What we take |
|---|---|
| **Hebbia** | Every answer links to the exact passage in the source. Citation previews show the source without breaking the user's flow. Process is visible, not a black box. |
| **AlphaSense** | Citations open a source viewer with the passage highlighted. Answers sit in a right side panel next to the document. A "Threads" list keeps past questions. Related questions after each answer. |
| **Perplexity** | Answer first, then sources. Numbered inline citations. A sources row under the answer. Chips that open a quick preview with 1/N paging. A "wrong sources" feedback option. |
| **Ramp** | Calm, white, precise. Near-black text, one accent, 4px spacing grid, Inter font, thin outline icons, very little decoration. |
| **Mosaic, Runway, Pigment** | (Later phases.) KPI cards on top, then variance and trend charts, then detail tables. Executives see the answer in seconds, analysts can prove it in minutes. Scenario comparison as a table next to charts. |

**One sentence brief:** a calm, white, dense-but-readable finance workspace where every number can be traced to its source in one click.

**Trust over decoration.** If a design choice does not help the user trust or verify a number, leave it out.

---

## 2. Core UI principles

1. **Answer first, proof one click away.** The answer is on top. Citations are inline. The source opens beside the answer, never on a new page that loses the chat.
2. **Never show an unverified number.** The UI only displays what the API returns after the output gate. The UI never calculates, rounds differently, or "fixes" a figure. Display only.
3. **Always show money context.** Every figure shows currency, units (thousands or millions), period and source. A bare number is a bug.
4. **"Insufficient data" is a normal, calm result.** Not an error screen. It explains what is missing and offers a next step (upload a document, ask differently).
5. **Say what is happening.** Uploading, reading, embedding, waking up, busy, retrying: each has a plain message. No silent spinners longer than 2 seconds.
6. **No raw errors, ever.** Every failure maps to one of the approved messages (section 9).
7. **The UI never decides access.** The server enforces roles. The UI only hides or disables things based on what the API says the user may do. Never write `if role === "..."` in components.
8. **Calm density.** Finance users like information. Use small type and tight spacing, but keep clear grouping, so it never feels cluttered.
9. **Keyboard and screen reader friendly** from the first screen (section 11).
10. **Boring and consistent beats clever.** Reuse the same component for the same job.

---

## 3. Tech baseline (proposal, confirm before adding)

The Phase 1 plan already fixes Next.js and an OpenAPI generated client. The items below are proposals. Per `CODING_STANDARDS.md` section 18, state a short reason in the pull request before adding any library.

- Next.js (App Router) with TypeScript strict mode.
- Tailwind CSS with design tokens as CSS variables (section 4).
- shadcn/ui (Radix based) for accessible primitives: dialog, popover, tooltip, tabs, sheet, command menu. Copy components into the repo, then restyle with our tokens.
- Icons: `lucide-react`, outline style, 1.5px stroke.
- Charts (Phase 2): Recharts or Visx. Decide in Phase 2.
- Document rendering for the source viewer: render server provided page content first. If a PDF page view is needed, use `pdf.js` with a highlight overlay. Decide in the source viewer slice.
- API client: generated from the OpenAPI contract. Never hand write fetch calls to the API.
- Streaming: Server-Sent Events or fetch streaming, as the API contract defines.
- Tests: Vitest and React Testing Library for components, Playwright for key flows, `axe` for accessibility checks.

**Hard rules**
- No hard-coded API URLs, limits, timeouts, role names, category lists or labels that come from config or the API. Read them from the API or one frontend config module.
- Only one frontend config module reads environment variables.
- No `localStorage` for tokens or any company data. Sessions follow the Cognito setup in the plan.
- No client side maths on money. Format with `Intl.NumberFormat` only. Values arrive as strings or integers with currency and units, never floats that we compute with.

---

## 4. Design tokens

All styling comes from tokens. No raw hex values or pixel values in components.

### 4.1 Colour (light theme is the Phase 1 default)

Dark theme is out of scope for Phase 1, but every colour must be a token so it can be added later.

```css
:root {
  /* Surfaces */
  --bg-canvas: #FAFAF9;       /* page background */
  --bg-surface: #FFFFFF;      /* cards, panels */
  --bg-subtle: #F4F4F2;       /* table header, hover, code */
  --bg-inverse: #18181B;      /* primary button */

  /* Text */
  --text-primary: #18181B;
  --text-secondary: #52525B;
  --text-muted: #71717A;
  --text-inverse: #FFFFFF;

  /* Borders */
  --border-subtle: #E7E5E4;
  --border-strong: #D6D3D1;

  /* Accent (links, citations, focus) */
  --accent: #3B4BDB;
  --accent-subtle: #EEF0FF;
  --focus-ring: #3B4BDB;

  /* Evidence highlight (cited text in the source viewer) */
  --highlight: #FFF3A3;

  /* Status (never colour alone, always with icon or text) */
  --positive: #15803D;  --positive-subtle: #ECFDF3;
  --negative: #B42318;  --negative-subtle: #FEF3F2;
  --warning:  #B54708;  --warning-subtle:  #FFFAEB;
  --info:     #175CD3;  --info-subtle:     #EFF8FF;
}
```

Rules:
- One accent colour only. Primary buttons are near-black. The accent is for links, citation chips, focus and selected states.
- Yellow is reserved for the evidence highlight, like a highlighter on a printed report. Do not use it anywhere else.
- Red and green carry meaning (down and up) only. Never use them for decoration.
- Text contrast must meet WCAG AA (4.5:1 body, 3:1 large text and icons).

### 4.2 Typography

- Font: **Inter** with a system fallback stack. Self host the font files (data residency and speed). Do not load fonts from a third party at runtime.
- Numbers: always `font-variant-numeric: tabular-nums` in tables, KPI cards and any column of figures.
- Mono (`JetBrains Mono` or system mono) only for ids and code.

| Token | Size / line height | Weight | Use |
|---|---|---|---|
| `text-xs` | 12 / 16 | 500 | Labels, captions, chips |
| `text-sm` | 14 / 20 | 400, 500 | Default UI text, tables, citations |
| `text-base` | 16 / 24 | 400 | Chat answers, long reading |
| `text-lg` | 18 / 26 | 600 | Section titles |
| `text-xl` | 24 / 30 | 600 | Page titles |
| `text-kpi` | 32 / 36 | 600 | KPI numbers (Phase 2) |

Letter spacing 0 for body. Slightly negative (-0.01em) for `text-xl` and above. Maximum two weights per screen (400 and 600, with 500 for small labels).

### 4.3 Spacing, radius, elevation

- **4px grid.** Allowed spacing: 4, 8, 12, 16, 20, 24, 32, 48. Default gap between related items is 8. Between groups, 24.
- Radius: `sm 4` (chips, badges), `md 8` (inputs, buttons, cards), `lg 12` (dialogs, popovers), `full` (avatars, pills).
- Elevation: prefer 1px borders over shadows. One soft shadow token for popovers and dialogs only. No shadow on cards.
- Content widths: chat column 720px max, app container 1280px max. Sidebar 240px, collapses under 900px.

### 4.4 Motion

- Duration 120 to 200ms, ease-out. Only for opening panels, popovers, and state changes.
- No bouncing, no typewriter effect, no decorative animation.
- Respect `prefers-reduced-motion`: turn all motion off.

### 4.5 Icons

Outline, 1.5px stroke, 16 / 20 / 24px. Icon only buttons always have an accessible label and a tooltip.

---

## 5. App layout

```
+---------+-------------------------------------------+------------------+
| Sidebar | Main area                                 | Right panel      |
| 240px   | (chat, documents, upload)                 | (source viewer)  |
|         |                                           | 420 to 560px     |
+---------+-------------------------------------------+------------------+
```

- **Sidebar:** product name, company name, nav (Ask, Documents, plus items that arrive in later phases), recent questions list ("Threads"), user menu at the bottom (name, role, sign out).
- **Main area:** one job per screen. Page title top left, primary action top right.
- **Right panel:** opens when a citation is clicked. It pushes the chat narrower on desktop (does not cover it). It can be closed with `Esc`. On screens under 900px it becomes a bottom sheet that covers the screen.
- **Top bar:** only if needed (breadcrumbs, status banner). A status banner (for example "Documents are still processing") appears here, not as a popup.
- Navigation items come from what the API says the user may access. A role with no access to a screen never sees the link.

---

## 6. Phase 1 screens

### 6.1 Sign in

- Cognito hosted or embedded sign in. Centered card, product name, email and password, one primary button.
- Clear message for wrong password, locked account, and the "login is temporarily unavailable" case (risk 6). Never expose raw Cognito errors.
- After sign in, land on **Ask** (or **Documents** if the role cannot ask questions, such as System Admin).

### 6.2 Ask (chat screen)

This is the hero screen. Model it on Perplexity and AlphaSense: answer first, citations inline, sources one click away.

**Layout**
- Empty state: a centered question box, three example questions built from this company's real categories (never invented figures), and a line showing the data scope ("Searching 124 documents, latest versions only").
- Conversation state: message thread in a 720px column, question box pinned to the bottom.
- Left sidebar lists past questions (threads). Selecting one reopens it.

**Question box**
- Multi line input, `Enter` sends, `Shift+Enter` adds a line, send button with label for screen readers.
- Optional scope filters (company is fixed): period, document category, document. Show active filters as removable chips above the answer.
- Disabled while an answer is streaming, with a visible "Stop" button.

**Answer block (top to bottom)**
1. A short status line while working: "Searching documents", "Checking numbers", "Verifying sources". Plain words, no model names. These map to real steps and are optional detail, not decoration.
2. The answer text (`text-base`).
3. Inline citation chips after the claim they support.
4. **Sources row** under the answer: stacked document icons plus "N sources". Click opens the right panel with every source listed.
5. Supporting figures table when the answer contains numbers (see 6.2.2).
6. Actions: copy, thumbs up, thumbs down. Thumbs down opens quick reasons: "Wrong numbers", "Wrong sources", "Out of date", "Incomplete". Feedback stays inside the company (plan rule).
7. Related questions (2 or 3), only if the API returns them.
8. A small meta line: "Based on latest final versions" and a cached badge if the answer came from cache.

**6.2.1 Streaming behaviour (important)**
The output gate holds back each sentence until its citations and numbers are verified. So the UI receives whole verified sentences, not tokens.
- Append sentence by sentence with a short fade. Do not fake a typewriter effect.
- Show the status line until the first sentence arrives. First response target is p95 3 seconds, so a skeleton of two lines is enough.
- If the answer ends early with a message (check failed after the first sentence), show the message in place, inside the same answer block, with a neutral style. Never delete sentences already shown.
- Never show an unverified or partial sentence.

**6.2.2 Numbers in answers**
- Figures render with currency, units and period, for example `USD 1,240.5 thousand, Q3 2026`.
- Right align, tabular numbers, thin space thousands separators per locale from `Intl`.
- Negative numbers use a minus sign. Colour red only as a second signal, never the only one.
- A figure computed by code carries a small "calculated" tag. Hover shows the inputs and their sources. A figure read directly from a document carries its citation chip.
- Show "Needs review" badge on any figure the API marks as low confidence.

**6.2.3 Citation chip**
- Format: `[1]` numbered, accent colour, 4px radius, minimum 24px tap target.
- Hover or focus opens a **preview popover** (Hebbia and Perplexity pattern): document name, version, page, table id, status (draft or final), and a two line excerpt. If one claim has several sources, add `1/3` paging inside the popover.
- Click opens the right panel at that exact place.
- The chip always has an accessible name, for example "Source 1: Q3 Board Report, page 12, table 4".
- A chip without a valid citation never renders. The API must not send one, and the UI must refuse to display an answer block with zero citations (except an "insufficient data" result).

**6.2.4 Special results**

| Result | How it looks |
|---|---|
| Insufficient data | Neutral card with an info icon. Title: "I don't have enough data to answer this." Body says what is missing if the API provides it. Actions: "Upload a document", "Rephrase". No red. |
| Needs review | Warning badge on the document or figure, with "Why?" explanation. |
| Busy | Inline notice in the thread: "We're busy right now. Please try again in a moment." with a "Try again" button. |
| Waking up | Inline notice with a progress style: "Waking up, please wait." Auto retries. Shows only after 2 seconds of waiting. |
| Temporarily unavailable | Inline notice: "Temporarily unavailable, please try again." with a "Try again" button. |
| Permission denied | "You don't have access to this." No detail on what exists. |

### 6.3 Source viewer (right panel)

Model it on AlphaSense (passage highlighted in the original) and V7 style bounding boxes. This is the screen that proves our citation promise.

**Header:** document title, category, period, version number, status badge (Draft / Final), page indicator ("Page 12 of 48"), close button, "Open full document" link (if allowed).

**Body**
- Show the cited content in a renderable shape: text with the cited span highlighted (`--highlight`), or the table as a real table with the cited cell or row highlighted. Never flatten tables to text.
- Show the page number and table title above the content. Show currency and units next to table headers.
- Scroll to the highlight automatically. Keep a few lines of context above and below.
- If one answer has several citations, show a list at the top: `1  2  3 ...`. Next and previous buttons (`J` and `K` shortcuts) move between them.
- If the document has a newer version than the one cited, show a calm banner: "A newer version exists." with a link. Do not swap the content silently.
- If the document was deleted or the user lost access, show "This source is no longer available." Never show another company's data.

**Footer:** "Copy citation" (document, version, page, table), and "Report wrong source".

**States:** loading skeleton, error (approved messages only), empty (should not happen, treat as error).

### 6.4 Documents

A table of the company's documents. Calm, dense, sortable.

- Columns: Name, Category, Period, Status (Draft / Final), Version, Ingestion state, Uploaded by, Updated.
- Ingestion state badges follow the job state machine: **Received, Stored, Processing, Ready** (shown only after commit), **Needs review**, **Failed**. Use icon plus text.
- Row click opens a detail drawer: versions list (kept for the retention period), pages count, "may be affected" flags (plan rule), and actions the role allows (Update, Delete).
- Filters: category, period, status, state. Search by name.
- Empty state: "No documents yet" with an Upload button. If the partition is missing, show the partition message from the API.

### 6.5 Upload

Strict form, matching the plan. All values come from the API or config, never hard-coded.

Fields:
1. **Upload type** (New, Update, Delete) as a segmented control. Chosen first, because it changes the form.
2. **Document category** (select, list from `documents.categories` via API).
3. **Period** (`YYYY-QX` or `YYYY-MM`, with a clear format hint and validation).
4. **Status** (Draft or Final).
5. **Replaces document** (searchable select, shown and required only for Update).
6. **File picker** with drag and drop. Allowed types: PDF, XLSX, XLS, CSV, DOCX. Show the size limit from the API.

Behaviour:
- Validate on blur and on submit. Error text sits under the field in plain words.
- **Duplicate check:** if the API finds a likely duplicate, show a warning card above the submit button: "This looks like an existing document." with two buttons: "Update the existing one" (switches the form to Update and prefills it) and "Upload as new anyway".
- Direct upload to the pre-signed link with a real progress bar per file. Then the virus scan step shows "Checking file". Rejected files show a clear message.
- After upload, route to the Documents table with the new row highlighted, and show its ingestion state live (poll or push, per API contract).
- Scanned or low confidence documents show "Needs review" with the reason after processing.
- Partition missing: block the form and show the API message. Do not let the user fill in everything first.
- Delete: confirmation dialog stating the soft delete period from the API ("Can be restored for 30 days"). Require typing nothing, but use a clear destructive button style.

### 6.6 Role aware behaviour (Phase 1 gate)

The four roles are Executive Leadership, Corporate Finance & Planners, Audit & Compliance, System Admin. Permissions come only from the API (which reads `permissions.yaml`).

- Hide navigation items the user cannot use.
- Disable (with tooltip explaining why) actions that are visible but not allowed, only when showing the control helps the user understand the product.
- System Admin sees no financial content: no Ask screen, no source viewer content. They land on user and settings screens (built when the API provides them).
- Audit & Compliance gets a read only experience: no upload buttons.
- Role labels in the UI use the display names above, never raw group ids.
- A direct visit to a forbidden URL shows the permission denied page, never a blank page or a redirect loop.

---

## 7. Later phase direction (do not build in Phase 1)

Design tokens and components must be ready for these, but screens wait for their phase.

**Dashboard (Phase 2)**
- Order: KPI cards, then trend and variance charts, then detail table. Executives see the answer in seconds, analysts can drill down.
- KPI card: label, value (`text-kpi`), delta badge (up or down with icon, period compared), tiny sparkline. Click opens a drill down. Every KPI links to its source documents.
- Time range control: 7D, 30D, 90D, 1Y, custom. Period and currency selectors in the page header.
- Charts: thin lines, light gridlines, direct labels where possible, one accent plus greys. Max 5 series. Always give a table view toggle and an accessible text summary. Export as image or PDF.
- Stale data: when a document update marks metrics stale, show a "Updating, figures may change" badge on affected cards (plan rule).

**Forecast and scenarios (Phase 3)**
- Scenario picker at the top (Base, Downside, custom), scenario comparison table next to the chart, editable assumptions in a side panel, impact shown instantly. Forecast ranges shown as a shaded band with a clear "Forecast" label.

**Alerts and risk (Phase 3)**
- Alert list with severity icon plus text, the metric, the threshold, and a link to the source. Acknowledge and snooze actions.

**Decisions and approvals (Phase 3)**
- Recommendation card: recommendation, reasoning, confidence level, sources, and an Approve button visible only to roles the API allows. Show a banner if the numbers underneath changed after the recommendation was made.

**Reasoning loops (Phase 3)**
- Hard questions run as queued jobs. Show "Working on it" with step list and an estimated state, plus a notification when done. Never block the chat with a long spinner.

---

## 8. Component rules

- One component, one job, one file. Same size limits as `CODING_STANDARDS.md` (about 300 lines per file, about 30 lines per function).
- Presentational components take data through props. They never call the API directly. Data fetching lives in hooks or route level loaders.
- No business rules in components. Formatting only.
- Every component has: loading, empty, error and success states, and a test or story for each.
- Core component list for Phase 1: `AppShell`, `Sidebar`, `PageHeader`, `Button`, `Input`, `Select`, `SegmentedControl`, `FileDropzone`, `ProgressBar`, `Badge`, `StatusPill`, `DataTable`, `EmptyState`, `InlineNotice`, `Dialog`, `Drawer`, `Popover`, `Tooltip`, `QuestionBox`, `AnswerBlock`, `CitationChip`, `CitationPreview`, `SourcesRow`, `FiguresTable`, `SourcePanel`, `FeedbackBar`.
- Buttons: one primary (near-black) per screen area. Secondary is outlined. Destructive is red, used only for delete.
- Badges and pills: icon plus text, never colour only.
- Tables: sticky header, row hover, numeric columns right aligned, 40px row height, keyboard navigable.
- Forms: label above the field, helper text under, error text replaces helper text, required fields marked in words ("Required"), not only an asterisk.
- Dialogs: focus trapped, `Esc` closes, focus returns to the trigger.

---

## 9. Copy and messages

Plain, calm, short. No jargon, no blame, no exclamation marks. No emoji.

Approved system messages (from the plan and config guide). Use exactly these meanings. Keep the text in one messages file so it can be translated later.

| Situation | Message |
|---|---|
| Database waking (pilot) | "Waking up, please wait." |
| Capacity full or queue wait too long | "We're busy right now. Please try again in a moment." |
| All models or embedding failed | "Temporarily unavailable. Please try again." |
| No evidence | "I don't have enough data to answer this." |
| Scan rejected (`scan_reader: none`) | "Scanned files can't be read in this setup. Please upload a digital file." |
| Low confidence read | "Needs review. Some numbers couldn't be read with confidence." |
| Partition missing | Show the API message. Fallback: "This company isn't set up for uploads yet. Please contact your administrator." |
| Duplicate found | "This looks like an existing document. Update it instead?" |
| Permission denied | "You don't have access to this." |
| Session ended | "Your session ended. Please sign in again." |

Rules:
- Error messages say what happened, then what to do next.
- Button labels are verbs: "Upload document", "Ask", "Try again".
- Use "document" and "source" consistently. Do not mix "file", "doc" and "record".
- Dates and numbers follow the user's locale through `Intl`. Periods display as written in the upload form ("Q3 2026").

---

## 10. Responsive behaviour

- Desktop first (finance users work on laptops), but every Phase 1 screen must work on a phone.
- Breakpoints: 640, 900, 1280.
- Under 900px: sidebar becomes a menu drawer, the source viewer becomes a full height bottom sheet, tables scroll horizontally inside their own container (never the page).
- Tap targets at least 44px on touch screens.
- A mobile app is out of scope for v1 (parent plan). Responsive web is enough.

---

## 11. Accessibility (required, not optional)

- WCAG 2.2 AA is the target.
- Every interactive element is reachable and usable with the keyboard, with a visible focus ring (`--focus-ring`, 2px, 2px offset).
- Logical heading order. One `h1` per page.
- Streaming answers use an `aria-live="polite"` region so screen readers hear new verified sentences without repeating the whole answer.
- Citation chips, status pills and charts never rely on colour only.
- Tables use real `<table>` markup with header cells and scope.
- Respect `prefers-reduced-motion` and browser zoom up to 200%.
- Run `axe` in CI on every Phase 1 screen. A new serious or critical issue fails the build.

Keyboard shortcuts (shown in a help dialog, `?` opens it):
`/` focus the question box, `Esc` close panel or dialog, `J` and `K` next and previous citation in the viewer, `Cmd or Ctrl + K` command menu.

---

## 12. Performance targets for the UI

These support the parent latency goals (first streamed response p95 3s, p99 5s, p99.9 7s).

- Render a skeleton and the status line within 100ms of sending a question.
- Never wait for the full answer before painting. Paint each verified sentence as it arrives.
- Lazy load the source viewer, charts and `pdf.js`. The Ask screen first load stays small.
- Keep the question box responsive at all times. No blocking work on the main thread.
- Show a "Waking up" notice only after 2 seconds, and a "Still working" notice after 8 seconds.
- Largest Contentful Paint under 2.5s on a normal laptop connection for the Ask screen.

---

## 13. Security in the UI

- Every request carries auth. The UI never builds a `company_id` itself. It comes from the authenticated session or the API.
- Never render answer or document HTML directly. Sanitize anything that can contain markup. Document text is data, not instructions and not trusted markup.
- Source links are opened through the source viewer API only. Never build links to storage objects in the browser.
- Pre-signed upload links are used once and not stored.
- No sensitive data in URLs, query strings, page titles, analytics events or console logs.
- Show the company name and role in the user menu so users always know which workspace they are in.
- Cached answers display a small "cached" badge (plan rule). The user can re-run the question.

---

## 14. Testing

- Component tests: every component, all four states (loading, empty, error, success).
- Screen tests (Playwright): sign in, upload (new, update, delete, duplicate), ask question, click a citation and see the highlight, insufficient data, busy, waking up, permission denied.
- Role tests: run the key flows for each of the four roles and check what is visible and hidden.
- Cross-company test: with two test companies, a citation id from company A must never open content for company B (the API blocks it, the UI must show permission denied).
- Accessibility tests with `axe` on every screen.
- Visual snapshot tests for tokens and core components.
- No real model calls and no real network in unit tests. Use the generated API client with fakes.

---

## 15. Working rules for the coding agent

1. Read this file, `CODING_STANDARDS.md` and `phase1_mvp_plan.md` before starting a UI task.
2. Plan first: list the screens, components and files you will add, and which API endpoints they use. Ask if unsure.
3. Build tokens and core components first, then one screen at a time, in this order: AppShell, Sign in, Documents, Upload, Ask, Source viewer.
4. Use the generated OpenAPI client. If an endpoint or field you need is missing, stop and ask. Do not invent fields.
5. Do not add a library, a font, an icon set or a pattern without saying why.
6. Do not restyle or "clean up" unrelated screens in the same change.
7. When unsure about a value (size, colour, timing, limit), use a token or a config value with a clear name. Never guess inline.
8. After finishing, run the checklist in section 16 and report which items you checked.

---

## 16. UI checklist (use before every pull request)

- [ ] Only tokens used, no raw colours or pixel values
- [ ] Both loading, empty, error and success states exist
- [ ] No number is calculated or altered in the UI
- [ ] Every figure shows currency, units and period
- [ ] Every answer shows citations, or a proper "insufficient data" result
- [ ] Citation chip has preview, accessible name and opens the exact source place
- [ ] Only approved messages shown, no raw error can reach the user
- [ ] Access is driven by the API, no role names in component logic
- [ ] No sensitive data in logs, URLs, titles or analytics
- [ ] Keyboard use works, focus ring visible, `axe` passes
- [ ] Works at 640, 900 and 1280 widths
- [ ] Text comes from the messages file, not typed inline
- [ ] Tests added: component states, screen flow, role and accessibility
- [ ] Both paths of any switch that touches the UI are shown and tested (for example cached answer badge, waking message)

---

## 17. Research sources used for this document

Reviewed during design research. Visual details of private products were not inspected directly, so treat them as direction, not exact specs.

- Hebbia: citation previews that show source data without breaking flow, grid view that makes steps visible, source linked answers.
- AlphaSense: Generative Search side panel, inline citations that open the document viewer with the passage highlighted, Threads list, related questions, "Ask in Doc".
- Perplexity (UX teardowns): numbered inline citations, sources row, right side sources panel, chip popovers with 1/N paging, "Wrong sources" feedback, layered trust pattern.
- Ramp (public design system extractions): white canvas, near-black text, single accent, Inter or similar sans, 4px grid, outline icons.
- Mosaic, Runway, Pigment (public product pages and reviews): KPI cards, scenario comparison tables, variance first dashboards, AI explanations of metric changes inside the dashboard.
- General AI UX citation pattern guidance: use both inline chips and a sources panel, avoid footnote only lists, avoid anonymous markers without publisher identity.
