# FinSight AI: UI Standards (v2, matched to the final prototype)

For the coding agent and every developer building the frontend. Read this before writing any UI code. If a task clashes with this file, `CODING_STANDARDS.md` or the parent plan, stop and ask. Do not quietly break a rule.

Related files: `finsightAI.md`, `finsight_config_switches.md`, `finsight_known_risks.md`, `phase1_mvp_plan.md`, `CODING_STANDARDS.md`.

What changed in v2: the final HTML prototype is now the visual source of truth. This file adds everything the prototype shows that v1 did not cover (sidebar, command menu, Settings, Dashboard, Charts, Reports, recycle bin, full responsive rules, component sizes, API needs). It also lists where the prototype and the plan disagree (section 21) so nobody builds a guess.

---

## 0. How to use this file and the prototype

**Prototype location:** `prototype/` at the repository root (12 files plus `README.md`: `styles.css`, `shell.js`, `charts.js`, `login.html`, `ask.html`, `documents.html`, `upload.html`, `dashboard.html`, `charts.html`, `reports.html`, `settings.html`, `not-allowed.html`). This is the user-supplied binding source from #345; `reports.html`, `not-allowed.html` and the five-pane `settings.html` are user additions retained in it. See `prototype/README.md` for viewing and conventions.

**Who wins when two sources disagree**

| Question | Winner |
|---|---|
| How it looks (layout, spacing, sizes, colours, text, states, order of things) | The prototype |
| How it behaves for security, access, numbers, company separation, API use | This file and `CODING_STANDARDS.md` |
| What is in scope for a phase | `phase1_mvp_plan.md` and the parent plan (see section 6 and section 21) |

**Prototype is a picture, not code to copy.** It is plain HTML, CSS and JavaScript with sample data. Build the real screens in Next.js with the generated API client. Port the CSS variables from `styles.css` as they are. Re-create the layouts and states. Do not copy the prototype scripts.

**Prototype only. Never ship these**
- The "Preview as" role box in the sidebar and the "State" dropdown under it.
- The "Sign in as" box and the "Show: wrong password, session ended, unavailable" links on the login page.
- The role stored in `sessionStorage` and the `can` table in `shell.js` (the real app gets this from the API).
- Fake timers, sample data and the words "Sample data" in page headers.
- The `#partition` hash and the "Prototype:" help lines on the upload page.
- The reload on resize in `shell.js` (the real charts redraw without a reload).
- Any number the prototype works out itself (deltas, shares, totals). The real app shows what the API sends (rule 2 in section 2).

**Specified by standard or ticket, not drawn in the prototype** (see ADR-0014): the Cognito-hosted MFA challenge for privileged roles; API-driven pagination in Documents; `Draft`/`Estimated` dashboard badges alongside `Updating`; "Figures are being prepared."; the inline "layout changed elsewhere" notice; the source-viewer loading, error, newer-version, needs-review, unavailable/no-access and conditional "Open full document" states; chart export metadata and opaque filenames; and the absence of permission-denied controls. These have no prototype visual to compare against, so a person signs off their snapshots. The prototype's title-based export filenames, `window.print()` PDF, Push column, "Mentions" event and full-screen chart premise are not accepted behaviour.

---

## 1. Design direction (what we are copying and why)

We studied products that finance and research teams already trust. We take one lesson from each. We do not copy their branding.

| Reference | What we take |
|---|---|
| **Hebbia** | Every answer links to the exact passage in the source. Citation previews show the source without breaking the user's flow. Process is visible, not a black box. |
| **AlphaSense** | Citations open a source viewer with the passage highlighted. Answers sit next to the document. A list of past questions. Related questions after each answer. |
| **Perplexity** | Answer first, then sources. Numbered inline citations. A sources row under the answer. Chips with a quick preview. A "wrong sources" feedback option. |
| **Ramp** | Calm, white, precise. Near-black text, one accent, 4px grid, Inter font, thin outline icons, very little decoration. |
| **Mosaic, Runway, Pigment** | (Phase 2 and later.) KPI cards on top, then variance and trend charts, then detail tables. |

**One sentence brief:** a calm, white, dense-but-readable finance workspace where every number can be traced to its source in one click.

**Trust over decoration.** If a design choice does not help the user trust or verify a number, leave it out.

---

## 2. Core UI principles

1. **Answer first, proof one click away.** The answer is on top. Citations are inline. The source opens beside the answer (or as a sheet on phones), never on a new page that loses the chat.
2. **Never show an unverified number, and never work one out in the UI.** The UI only displays what the API returns after the output gate. It does not add, subtract, round differently, or work out changes and shares. Display only.
3. **Always show money context.** Every figure shows currency, units (thousands or millions), period and source. The context may sit in the column header, card subtitle or caption (as the prototype does) instead of repeating on each number. A figure with no context anywhere near it is a bug.
4. **"Insufficient data" is a normal, calm result.** Not an error screen. It explains what is missing and offers a next step.
5. **Say what is happening.** Uploading, reading, embedding, waking up, busy, retrying: each has a plain message. No silent spinner longer than 2 seconds.
6. **No raw errors, ever.** Every failure maps to one of the approved messages (section 12).
7. **The UI never decides access.** The server enforces roles. The UI shows or hides things from the capabilities the API returns (section 17). Never write `if role === "..."` in components.
8. **Calm density.** Small type and tight spacing, with clear grouping.
9. **Keyboard and screen reader friendly** from the first screen (section 14).
10. **Boring and consistent beats clever.** Reuse the same component for the same job.
11. **One design, every screen size.** Phone, tablet, laptop and wide desktop all work. No page ever scrolls sideways (section 13).

---

## 3. Tech baseline (proposal, confirm before adding)

The Phase 1 plan fixes Next.js and an OpenAPI generated client. The rest are proposals. Per `CODING_STANDARDS.md` section 18, state a short reason in the pull request before adding any library.

- Next.js (App Router) with TypeScript strict mode.
- Tailwind CSS with the design tokens in section 4 as CSS variables. Tailwind classes must read the tokens. No raw colours.
- shadcn/ui (Radix based) for accessible primitives where it saves time: dialog, popover, tooltip, tabs, sheet, command menu. Restyle every one to match the prototype exactly.
- Icons: outline, 16px, 1.5px stroke, round caps. Use the same shapes as the prototype symbols. `lucide-react` is fine where the shape is the same.
- Charts: the prototype draws plain SVG. Build the same look with Recharts or Visx or plain SVG components. Decide in Phase 2.
- Source viewer: render the server-provided text and table content first (as the prototype does). Use `pdf.js` only if a real page image is needed.
- API client: generated from the OpenAPI contract. Never hand write fetch calls to the API.
- Streaming: Server-Sent Events or fetch streaming, as the API contract defines.
- Native `<dialog>` or Radix Dialog for dialogs (focus trap and Esc for free).
- Tests: Vitest and React Testing Library, Playwright for flows and the width sweep, `axe` for accessibility.

**Hard rules**
- No hard-coded API URLs, limits, timeouts, role names, category lists or labels that come from config or the API.
- Only one frontend config module reads environment variables.
- No `localStorage` for tokens or any company data. One allowed exception: UI-only settings with no company data (for example the sidebar collapsed or open choice, key `fs_side`).
- No client side maths on money. Format with `Intl.NumberFormat` only. Values arrive as strings or integers with currency and units.
- Self-host the Inter font files (data residency and speed). The prototype only names the font and falls back to the system stack.

---

## 4. Design tokens

All styling comes from tokens. No raw hex values or pixel values in components. Copy this block into the global stylesheet as is. It equals `:root` in the prototype `styles.css`, plus the extra tokens the prototype hard-coded (marked **new**).

### 4.1 Colour and other tokens (light theme is the default)

Dark theme is out of scope for Phase 1, but every colour must be a token so it can be added later.

```css
:root {
  /* Surfaces */
  --bg-canvas:#FAFAF9; --bg-surface:#FFFFFF; --bg-subtle:#F4F4F2; --bg-inverse:#18181B;
  --bg-inverse-hover:#2C2C31;                 /* new: primary button hover */

  /* Text */
  --text-primary:#18181B; --text-secondary:#52525B; --text-muted:#71717A; --text-inverse:#FFFFFF;

  /* Borders */
  --border-subtle:#E7E5E4; --border-strong:#D6D3D1;

  /* Accent (links, citations, focus) */
  --accent:#3B4BDB; --accent-subtle:#EEF0FF; --focus-ring:#3B4BDB;

  /* Evidence highlight (cited text in the source viewer) */
  --highlight:#FFF3A3;

  /* Status (never colour alone, always with icon or text) */
  --positive:#15803D; --positive-subtle:#ECFDF3;   /* subtle: new */
  --negative:#B42318; --negative-subtle:#FEF3F2;   /* subtle: new */
  --warning:#B54708;  --warning-subtle:#FFFAEB;  --warning-border:#FEDF89;  /* border: new */
  --info:#175CD3;     --info-subtle:#EFF8FF;     --info-border:#B2DDFF;     /* border: new */

  /* Overlays */
  --scrim:rgba(24,24,27,.35);                 /* new: menu, command menu, sheet */
  --scrim-light:rgba(24,24,27,.25);           /* new: side drawers (Documents, Reports, Dashboard) */

  /* Spacing, radius, elevation, font */
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:20px; --s6:24px; --s7:32px; --s8:48px;
  --r-sm:4px; --r-md:8px; --r-lg:12px;
  --shadow-pop:0 8px 24px rgba(24,24,27,.12);
  --font:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
```

Rules:
- One accent colour only. Primary buttons are near-black. The accent is for links, citation chips, focus, selected chart points and selected states.
- Yellow (`--highlight`) is only for the evidence highlight in the source viewer.
- Red and green carry meaning (down and up, unfavorable and favorable) only. Never decoration.
- Text contrast meets WCAG AA (4.5:1 body, 3:1 large text and icons).
- The prototype uses a few raw hex values (`#ECFDF3`, `#FEF3F2`, `#B2DDFF`, `#FEDF89`, `#2c2c31`, `#fff`). In the real code each one must use its token above.

### 4.2 Typography

- Font: **Inter**, self-hosted, with the system fallback stack in `--font`.
- Numbers: `font-variant-numeric: tabular-nums` in tables, KPI cards and any column of figures (class `num`).
- Mono only for ids, code and `kbd` keys. Audit action names (like `user.invited`) use mono.

| Token | Size / line height | Weight | Use |
|---|---|---|---|
| `text-2xs` | 11 / 16 | 500 | Key caps (`kbd`), small tags ("calculated"), prototype-style tiny labels |
| `text-xs` | 12 / 16 | 500 | Labels, captions, badges, hints, table headers |
| `text-13` | 13 / 18 | 400, 500 | Notices, compact buttons, settings sub links, status line, popover text |
| `text-sm` | 14 / 20 | 400, 500 | Default UI text, tables, citations |
| `text-base` | 16 / 24 | 400 | Chat questions and answers, long reading |
| `text-lg` | 18 / 26 | 600 | Section titles, the Ask page title, drawer titles |
| `text-xl` | 24 / 30 | 600 | Page titles (Documents, Upload, Settings, Dashboard and others) |
| `text-kpi` | 32 / 36 | 600 | KPI numbers (26 / 30 on phones) |

Letter spacing 0 for body, -0.01em for `text-xl` and above. Weights: 400 and 600, with 500 for small labels.

### 4.3 Spacing, radius, elevation

- **4px grid.** Allowed spacing: 4, 8, 12, 16, 20, 24, 32, 48 (the `--s1` to `--s8` tokens). Default gap between related items is 8. Between groups, 24.
- Radius: `sm 4` (chips, badges, tags), `md 8` (inputs, buttons), `lg 12` (cards, dialogs, popovers, sheets), `full` (avatars, pills, switches).
- Elevation: 1px borders, not shadows. `--shadow-pop` is only for popovers, menus, drawers, sheets, dialogs, the command menu and toasts. No shadow on cards.
- Content widths: chat column 720px max, Settings column 840px max, upload form 640px max, app container 1280px max.

### 4.4 Motion

- Duration 120 to 250ms, ease-out. Used for: drawers and sheets sliding (180ms), the sidebar width change (150ms), sentence fade-in in answers (250ms), toggles (150ms).
- Loading indicators may animate (spinner, indeterminate bar). No bouncing, no typewriter effect, no decorative animation.
- Respect `prefers-reduced-motion`: turn all motion off.

### 4.5 Icons

Outline, 1.5px stroke, round caps and joins, 12 / 16 / 20 / 24px. Icon only buttons always have an accessible label (and a tooltip on desktop). The prototype icon set: chat, document, upload, gear, chevron, dashboard, chart, report calendar, lock, menu, search, close, check, alert triangle, info circle, clock, spinner arc, error circle, plus, copy, thumbs up, thumbs down, send arrow, stop square, restore, up-down sort.

---

## 5. App shell (sidebar, top bar, command menu, shortcuts, access denied)

```
Desktop (901px and up)
+---------+-------------------------------------------+------------------+
| Sidebar | Main area                                 | Right panel      |
| 240px   | (page)                                    | 480px (Ask only) |
| (or 64) |                                           |                  |
+---------+-------------------------------------------+------------------+

Phone and small tablet (900px and down)
+-------------------------------------------+
| Top bar 48px: menu, FinSight AI, search   |
+-------------------------------------------+
| Main area (one column)                    |
+-------------------------------------------+
Sidebar becomes a drawer. Source panel becomes a bottom sheet.
```

### 5.1 Sidebar (desktop)

Top to bottom: collapse toggle (round 24px button on the right edge), product mark and name, company name (12px muted), **Search** button with the `Cmd K` or `Ctrl K` key hint, nav links (Ask, Dashboard, Charts, Reports, Documents, Upload), **Settings** group (expands to Profile, Notifications, Users, Audit log, Cost view), a scrolling slot (Ask puts "Recent questions" here), "Keyboard shortcuts" button with `?`, then the user block (avatar with initials, name, role display name).

- Width 240px. Collapsed width 64px: only icons show (labels, company, slot, user text hide), each link gets a `title` tooltip. Clicking Settings while collapsed expands the sidebar first.
- The collapsed or open choice is remembered (UI-only setting, see section 3).
- Nav items come from the API capabilities (section 17). A role with no access never sees the link. Current page has `aria-current="page"` and a subtle grey background.
- The Settings sub links also come from capabilities (Users, Audit log and Cost view only appear for roles that may use them). On desktop the Settings page has no second tab bar, the sidebar group does that job.
- Recent questions list: heading "Recent questions", one row per past question, ellipsis for long text, selected one has `aria-current`.

### 5.2 Top bar and drawer (900px and down)

- Fixed 48px bar: menu button (opens drawer), product mark and name, search button (opens command menu).
- Drawer: 280px wide (max 86vw), slides in from the left over a dim scrim. It has a close button, closes on scrim tap, link tap and `Esc`. Focus moves into the drawer when it opens and back to the menu button when it closes. The drawer is hidden from keyboard and screen readers when closed.
- Below the bar the page gets `padding-top: 48px`.

### 5.3 Command menu (`Cmd` or `Ctrl` + `K`)

- Centered dialog (max 560px) near the top, search field, result list, hint line "Up and down to move, Enter to open, Esc to close".
- Groups: **Go to** (pages the role may open), **Settings** (sections the role may open), **Help** (Keyboard shortcuts), **Account** (Sign out). Empty result: "No matching commands."
- ARIA: `combobox` input, `listbox` of `option`s, `aria-activedescendant`. Tab does not leave the dialog. Opens from the sidebar button, the phone search icon, and the shortcut.

### 5.4 Keyboard shortcuts help (`?`)

Table of keys: `/` focus the question box (Ask), `Esc` close a panel, menu or dialog, `J` next citation, `K` previous citation, `Cmd/Ctrl + K` command menu, `?` this help. Shortcuts do nothing while typing in a field. Hide the shortcuts button and key hints on touch devices.

### 5.5 Access denied page and in-page denial

Shown when the user opens a page the role may not use (a direct URL, or a link from old history). Centered: lock icon in a grey circle, heading "You don’t have access to this.", body "Your role, {role name}, can’t open this page. If you think this is a mistake, ask your administrator.", two buttons: primary **Go to {home page}** (Settings for System Admin, Dashboard for Executive Leadership once it exists, otherwise Ask) and **Go back**. Never a blank page or a redirect loop. The sidebar stays visible.

### 5.6 Toasts

Bottom right (full width with 12px margins on phones), `role="status"`, white card with border and `--shadow-pop`, green check icon, one line. Disappears after about 3 seconds. Used for "Saved", "Moved to the recycle bin", "Report is ready" and similar.

---

## 6. Screen inventory, roles and phases

The prototype shows more screens than Phase 1. Build in the phase shown. Do not build a later phase screen early (the phase plan wins). User additions retained in #349 are `reports.html`, `not-allowed.html` and the five-pane `settings.html`; the phase assignments below and the open decisions in section 21 still apply.

| Route | Prototype file | Who sees it | Phase |
|---|---|---|---|
| `/sign-in` | `login.html` | Everyone | 1 |
| `/ask` | `ask.html` | Executive Leadership, Corporate Finance & Planners, Audit & Compliance | 1 |
| Source viewer (panel on Ask) | `ask.html` | Same as Ask | 1 |
| `/documents` (Library and Recycle bin) | `documents.html` | All roles except System Admin, which is denied by the as-built matrix | 1 |
| `/upload` | `upload.html` | Corporate Finance & Planners | 1 |
| Access denied | `not-allowed.html` | Anyone who opens a page they may not use | 1 |
| `/settings/profile`, `/settings/notifications` | `settings.html` | All roles | 2 (all five panes accepted by #357 / ADR-0014) |
| `/settings/users` | `settings.html` | System Admin | 2 |
| `/settings/audit` | `settings.html` | System Admin, Audit & Compliance | 2 |
| `/settings/cost` | `settings.html` | System Admin, Executive Leadership | 2 |
| `/dashboard` | `dashboard.html` | All except System Admin | 2 |
| `/charts` | `charts.html` | All except System Admin | 2; this is the chart detail view (ADR-0014) |
| `/reports` | `reports.html` | All except System Admin (only Corporate Finance & Planners can change schedules or generate) | Not in Phase 2 acceptance; final placement with #360 |

Home page after sign in: System Admin goes to Settings (Profile). Corporate Finance & Planners and Audit & Compliance go to Ask. Executive Leadership goes to Ask in Phase 1 and to Dashboard once Phase 2 ships. The API tells the UI the home page (section 17).

---

## 7. Phase 1 screens

### 7.1 Sign in

- Centered column (max 400px). Product mark and name above a white card (radius 12, 32px padding, 20px on phones).
- Card: heading "Sign in", line "Ask questions about your financial documents. Every number links to its source.", message area, **Work email**, **Password** with a "Forgot password?" link on the same row as the label, primary full-width **Sign in** button (40px, 44px on phones).
- Under the card: "Your data stays in your company workspace." and "Need access? Contact your administrator."
- Messages (area above the fields, `role="alert"`): wrong details "That email or password doesn’t match. Check both and try again." (never say which one is wrong), session ended "Your session ended. Please sign in again." (info style), login down "Sign in is temporarily unavailable. Please try again in a few minutes." (warning style; fields and sign in button are disabled and a **Try again** button replaces it).
- Cognito hosted or embedded. Never show raw Cognito errors.
- The MFA challenge for System Admin and Executive Leadership is provider-hosted and recorded as "specified by standard, not drawn"; no new app-designed MFA screen is added in Phase 2 (ADR-0014).

### 7.2 Ask (chat screen)

The hero screen. Answer first, citations inline, sources one click away.

**Layout**
- Page bar: title "Ask" (18px) on the left, data scope text on the right ("Searching 124 documents, latest final versions"). Wraps under the title on narrow screens.
- Thread area (scrolls) with a 720px centered column, composer pinned at the bottom.
- Recent questions live in the sidebar slot.
- Empty state: heading "What would you like to know?" (24px), three example questions built from this company's real categories as full-width bordered buttons (max 480px), and the line "Searching 124 documents, latest versions only."

**Composer**
- One rounded box (border strong, radius 12, accent border on focus). Multi-line input (16px, 2 lines), `Enter` sends, `Shift+Enter` adds a line, `/` focuses it from anywhere.
- Under the input, inside the box: scope chips (pill, 28px) such as "Period: Q3 2026" with a remove icon and "All categories", then the send button on the right.
- Send button: 36px near-black square with an up arrow. While an answer streams it becomes a **Stop** button (square icon), the input is disabled, and the label changes to "Stop". Stopping shows "Stopped. Ask again or rephrase."
- On phones the composer has less padding and respects the bottom safe area.

**Question bubble:** right aligned, `--bg-subtle`, radius 12, max 85% wide, 16px text.

**Answer block (top to bottom)**
1. **Status line** while working: spinner plus plain words that change: "Searching documents", "Checking numbers", "Verifying sources" (no model names), with two skeleton lines under it. When done it becomes a green check and "Searched documents, checked numbers, verified sources".
2. Answer text (`text-base`), one paragraph per verified chunk, each fading in.
3. Inline **citation chips** after the claim they support.
4. **Figures table** when the answer has numbers (7.2.2).
5. *(Phase 2)* An inline chart card with Chart or Table toggle and a caption with its source chip. Do not build the inline chart in Phase 1, the chart API arrives in Phase 2.
6. **Sources row:** a bordered button with a document icon and "N sources" (opens the right panel at the first source). On the right: copy, thumbs up, thumbs down icon buttons.
7. Thumbs down opens a small menu: "Wrong numbers", "Wrong sources", "Out of date", "Incomplete". After a choice: "Thanks. Your feedback stays in your company." Feedback never leaves the company (plan rule).
8. Meta line (12px muted): "Based on latest final versions", plus a small **Cached** badge if the answer came from the cache (required by plan and section 16, with a re-run action).
9. **Related questions** (only if the API returns them): rows with an arrow, separated by top borders.

**7.2.1 Streaming behaviour (important)**
The output gate holds back each sentence until its citations and numbers are verified. The UI receives whole verified sentences, not tokens.
- Append sentence by sentence with a short fade (250ms). No typewriter effect.
- Show the status line and skeleton within 100ms of sending.
- If the answer ends early with a message (check failed after the first sentence), show the message in the same answer block with a neutral style. Never delete sentences already shown.
- Never show an unverified or partial sentence.

**7.2.2 Numbers in answers**
- Figures table: caption line with units and periods ("USD thousands, Q2 2026 vs Q3 2026"), header row, one row per item, right-aligned tabular numbers, an optional Change column.
- Number format: `Intl.NumberFormat("en-US")` for now (comma thousands separator, dot decimals). Percent shows 1 decimal, changes in margin show "pts" ("−3.4 pts"), days 0 decimals, months 1 decimal. Negative numbers use the real minus sign (U+2212), red as a second signal only.
- A figure computed by code carries a small grey **calculated** tag (11px, bordered). Showing the inputs and sources on hover is a later improvement. A figure read straight from a document carries its citation chip.
- Low confidence figure: **Needs review** warning badge in the cell, and a warning notice above the table: "Needs review. Some numbers couldn’t be read with confidence."

**7.2.3 Citation chip**
- Format: `[1]` numbered, accent colour on `--accent-subtle`, radius 4, 24px high on desktop, 28px on touch, 2px side margin. Hover or press fills it with the accent.
- **Mouse only:** hover or focus opens a preview popover (300px wide, fixed position, never clipped): document name, then "Version 2, Final, page 12, table 4", then a two line excerpt in a grey box. If one claim has several sources, add `1/3` paging. On touch screens the popover is off and a tap opens the source viewer directly.
- Click opens the source viewer at that exact place.
- Accessible name: "Source 1: Q3 Management Report, page 12, table 4".
- A chip without a valid citation never renders. The UI refuses to show an answer block with zero citations (except "insufficient data").

**7.2.4 Special results**

| Result | How it looks |
|---|---|
| Insufficient data | Bordered card, info icon, title "I don’t have enough data to answer this.", body from the API (what is missing, latest period available), buttons **Upload a document** (only if allowed) and **Rephrase** (focuses the input). No red. |
| Needs review | Warning notice and badge (7.2.2). |
| Busy | Warning notice in the thread: "We’re busy right now. Please try again in a moment." with **Try again**. |
| Waking up | Info notice with a clock icon, "Waking up, please wait." and an indeterminate bar. Appears only after 2 seconds of waiting. Auto retries. |
| Temporarily unavailable | Warning notice: "Temporarily unavailable. Please try again." with **Try again**. |
| Permission denied | Neutral notice with a lock icon: "You don’t have access to this." No detail about what exists. |

### 7.3 Source viewer (right panel)

Proves the citation promise. The prototype shows it as the Ask right panel.

**Header:** document title, a row of small facts (category, period, "Version 2", status badge Draft or Final), close button.
**Tab row:** one numbered button per citation in the answer (selected one is near-black), and "Page 12 of 48" on the right. `J` and `K` move between them. The tab list uses `role="tablist"`.
**Body:** a short context paragraph (13px, secondary), then the table title ("Table 4: Gross margin by quarter"), a units line ("Percent of revenue, USD thousands for revenue"), then the real table with the cited row or cell highlighted (`--highlight`, weight 500). For text sources, the cited span is wrapped in `mark`. Scroll the highlight into view with a few lines of context. Never flatten tables to text.
**Footer:** **Copy citation** (document, version, page, table) and **Report wrong source**.
**Also required, not drawn in the prototype yet:**
- Loading skeleton and error state (approved messages only).
- Banner "A newer version exists." with a link, when the cited version is not the latest. Never swap content silently.
- "This source is no longer available." when the document was deleted or access was lost. Never show another company's data.
- "Open full document" link in the header if the role may open it.
- "No longer available" and "no access" are the same non-leaking screen; a deleted citation must not be distinguishable from one the user may not see. The GET route must be mounted and enforce company, role and access scope before citation-click tests count (ADR-0014).
- At each width, `Esc` closes the viewer, focus returns to the citation chip, and the bottom sheet traps focus. These states are "specified by standard, not drawn" and get human-signed snapshots rather than a prototype comparison.

**Where it lives**

| Screen width | Behaviour |
|---|---|
| Over 1180px | 480px column on the right, pushes the chat narrower |
| 901 to 1180px | 480px panel floats over the chat from the right edge (max 92vw) with a shadow, chat keeps full width |
| 900px and down | Bottom sheet, up to 78% of screen height (max 640px), rounded top corners, a small grab bar, dim backdrop. Tap the backdrop, the close button or `Esc` to close. The sheet is not rendered when closed. |

### 7.4 Documents

Calm, dense, sortable. Two views switched by a segmented control: **Library** and **Recycle bin (N)**.

**Page bar:** "Documents", a sub line, and the primary **Upload document** button (only for roles that may upload).
**Notices (info style):** System Admin is denied the Documents page entirely under the as-built permission matrix (§7.6); there is no details-only variant. Recycle bin: "Deleted documents are kept for 30 days, then removed for good." (days come from the API).
**Filters:** search by name, category, status (Draft or Final), ingestion state. On phones also a **Sort by** select (Newest first, Oldest first, Name A to Z) because the column headers are hidden. The filters for status and state hide in the Recycle bin.
**Count line:** "8 documents" (`aria-live="polite"`). The prototype has no pager; acceptance requires an API-driven pager styled with existing tokens and committed snapshots, recorded as "specified by ticket, not drawn" (ADR-0014).

**Library table**

| Column | Notes |
|---|---|
| Name | Document icon and name, a small alert icon if "may be affected by a newer document". Sortable. |
| Category, Period | Plain text |
| Status | Draft (grey) or Final (green) badge |
| Version | `v2` |
| Ingestion state | Badge with icon and text: Received, Stored, Processing, **Ready** (only after commit), Needs review, Failed |
| Uploaded by, Updated | Updated is sortable and has `aria-sort` |

A newly uploaded row is highlighted with `--accent-subtle`. A row is focusable and opens on click or `Enter`.

**Recycle bin table:** Name, Category, Period, Version, Deleted by, Deleted ("2 days ago"), Purges in ("28 days"), and actions **Restore** and **Delete permanently** for upload-capable roles (view-only roles see "View only"). Delete permanently asks first: "Delete permanently? This removes the document and all its versions for good. This can’t be undone." The backend must enforce the purge before the button renders; reuse the `delete` category action only if it covers permanent purge, otherwise a dedicated action must be agreed by #359/#360. System Admin never sees this page or action (ADR-0014).

**Empty states:** "No documents match" with "Try a different search or clear the filters." and a **Clear filters** button; "The recycle bin is empty" with "Deleted documents stay here for 30 days."; "No documents yet" with an Upload button; partition missing shows the API message.

**Detail drawer** (right, 440px, full width on phones, dim scrim, closes with `Esc`): title, small facts (category, period, status badge, ingestion badge), then, when present: a warning notice for Needs review or Failed (reason text), a warning notice **"May be affected."** with the reason (for example another document for the same period), a **Details** list (Pages, Uploaded by, Updated), a **Versions** list (version, status badge, **Latest** badge, date) and "Older versions are kept for 365 days." Footer: **Update document** (goes to Upload with Update chosen) and **Delete** (destructive style), only for roles that may.
**Delete dialog:** "Delete this document? It moves to the recycle bin. You can restore it for 30 days." with Cancel and **Delete document**. Then a toast "Moved to the recycle bin."

### 7.5 Upload

Strict form in a white card (max 640px). All values come from the API or config. Only roles that may upload see this page.

Fields, in this order:
1. **Upload type**: segmented control with **New** and **Update**. (Delete is not here. It is done from Documents, see section 21.)
2. **Document to replace**: searchable field, shown and required only for Update. Choosing one prefills category, period and status.
3. **Document category** (select, from the API) and **Period** (side by side on wide screens, stacked on phones). Period format `2026-Q3` or `2026-09`, with a hint under the field.
4. **Status**: segmented **Draft** and **Final** (Final is the default).
5. **File** drop zone: dashed border, upload icon, "Drag files here or choose from your computer" (on touch screens: "Tap to choose files"), hint "PDF, XLSX, XLS, CSV, DOCX. Up to 50 MB each." (limit from the API). Multiple files allowed.

Behaviour:
- Validate on blur and on submit. Error text sits under the field in plain words and replaces the hint. Bad file type: "“name” can’t be uploaded. Use PDF, XLSX, XLS, CSV or DOCX." Too big: "“name” is larger than 50 MB."
- Each chosen file is a row: icon, name (ellipsis), size, remove button.
- **Duplicate check:** warning card above the buttons: "This looks like an existing document." with the matching document, then **Update the existing one** (switches to Update and prefills) and **Upload as new anyway**.
- On submit: real progress bar per file ("Uploading 40%"), then "Checking file" (virus scan), then "Queued for processing". Then an info notice "Your upload is queued. It will show as Ready when processing finishes." and a **View in Documents** button. In Documents the new row is highlighted and its state updates live.
- Partition missing: the whole form is replaced by a warning notice with the API message (fallback: "This company isn’t set up for uploads yet. Please contact your administrator.") and a **Back to Documents** link. Do not let the user fill in the form first.
- Low confidence or scanned documents show "Needs review" with the reason after processing.

### 7.6 Role aware behaviour (Phase 1 and 2 gate)

The four roles are Executive Leadership, Corporate Finance & Planners, Audit & Compliance, System Admin. Permissions come only from the API (which reads `permissions.yaml`); a page must never branch on a role name.

- If the API does not grant an action, its control is **absent from the DOM** — not disabled, not merely hidden by CSS. There is no "disabled with a tooltip" option for permission cases.
- Disabled state is reserved for reasons unrelated to access: Save before any change, a form awaiting required fields, or sign-in during an outage.
- Hide navigation items the user cannot use. A test per role asserts the forbidden controls are missing from the rendered page, not just visually hidden.
- System Admin sees no financial content: no Ask, no source viewer content, no Dashboard, Charts, Reports or Documents. "File details only" is not an as-built capability.
- Audit & Compliance gets a read only experience: no upload, update, restore or delete buttons.
- Role labels use the display names above, never raw group ids.
- A direct visit to a forbidden URL shows the access denied page (5.5) with the plain "You don’t have access to this." message, never a blank screen.

---

## 8. Settings (defined by the prototype, phase to be confirmed)

Layout: page bar "Settings", then a centered column (max 840px). Desktop: sections are chosen from the sidebar Settings group. 900px and down: a sticky tab bar (Profile, Notifications, Users, Audit log, Cost view) sits at the top of the page and scrolls sideways if needed. A forbidden or unknown section falls back to Profile. Each section is a bordered card (radius 12, 24px padding, 16px on phones).

**8.1 Profile (all roles)**
- Avatar (initials or photo) with **Change photo** and **Remove**. Hint "PNG or JPG, up to 2 MB." (turns red with "Use a PNG or JPG up to 2 MB." on a bad file).
- Fields: Full name, Email, Company (read only), Role (read only), with a lock line "Company and role are set by your administrator."
- Changing the email shows a "Verification code" field (6 digits) and **Verify email**. The API sends the code: "We sent a 6-digit code to {email}."
- **Cancel** and **Save changes** (Save is disabled until something changes). Errors: "Enter your name.", "Enter a valid email address.", "Enter the 6-digit code."

**8.2 Notifications (all roles)**
- A table: Event, Email, Push. Each cell is a switch. Changes save at once and a small "Saved" confirmation appears (`aria-live`). Hint "Push notifications also need permission in your browser."
- The event list comes from the API. The prototype sample list (Ingestion complete, Job failed, Dashboard stale, Mentions, Weekly digest) is not final (section 21).

**8.3 Users (System Admin)**
- Header with "N of 10 users" (limit from API, "Maximum reached." when full) and **Invite user**.
- Seat tiles, one per role: "Executive Leadership 2 of 3", and so on (4 across, 2 across on phones).
- Card with a switch: "Require multi-factor sign-in. Applies to System Admin and Executive Leadership. They set it up at next sign in."
- Table: User (name, "You" badge for yourself, email), Role, MFA (Enabled, Required not set up, Not set up), Status (Active, Invited), Last active, row menu (three dots) with actions such as change role, reset MFA, resend invite, deactivate. Menus and dialogs follow section 11.
- Hint "Role changes take effect within 60 seconds." (value from API).
- Every change is an audit log entry.

**8.4 Audit log (System Admin, Audit & Compliance)**
- Read only lock line: "Read only. Entries can’t be edited or deleted."
- Search field and action filter. Table: Actor, Action (mono, like `document.uploaded`), Resource, Detail, Timestamp. **Show more** loads the next page.

**8.5 Cost view (System Admin, Executive Leadership)**
- Month select. Four summary tiles. A **Monthly budget** card with a progress bar and a note. A daily spend bar chart (card with Chart or Table toggle). Tables: **By service** (Service, Usage, Cost USD, Share) and **Model calls** (Model, Used for, Calls, Tokens in and out, Cost USD). A reconcile note under them. All figures come from the metering rows through the API.

---

## 9. Phase 2 screens (reference only, do not build in Phase 1)

**9.1 Dashboard**
- Page bar: title, "As of Q3 2026" line, controls: period select, currency chip ("Currency: USD"), time range segmented control (4Q, 6Q, 8Q).
- When a document update is in progress, a warning notice at the top: "A document was updated. Figures marked Updating may change."
- **KPI grid** (auto-fill, cards at least 210px wide): Revenue, Gross margin, Net margin, Operating expenses, Cash flow, Burn rate, Runway, DSO, DPO, Budget vs actual. Each card is a button: label, optional "Updating, figures may change" warning badge, big number, "units, period", change badge with arrow (green when the change is good for that metric, red when bad, "pts" for percent metrics) and "vs Q2 2026", a small sparkline and "N sources". Click opens the metric drawer.
- **Trends:** two chart cards side by side (one column under 900px).
- **Budget vs actual** (only when budget data exists, otherwise the insufficient data card): three summary tiles, a variance chart card (rows sorted by largest gap, a centered zero line, bars left for below budget and right for above, badge Favorable or Unfavorable, table toggle), and a **Detail** table.
- **Metric drawer** (480px): number, change, short chart, how it was calculated, sources list, and an **Ask about this metric** button.
- States: loading skeleton cards, "No figures yet" card (with Upload button only if allowed), "Temporarily unavailable" notice with Try again.

**9.2 Charts**
- Left: "Build a chart" panel (280px). Chart type segmented (Trend, Comparison, Breakdown), metric, time range, periods to compare (choose 2 to 4, error "Choose at least 2 periods."), breakdown of, period. Right: chart card.
- Chart card: title, subtitle, **Chart or Table** toggle, **Image** and **PDF** export buttons, the chart, a caption "Source: ..." and a one-line text summary under it. Each chart has an `aria-label` with its values.
- 900px and down: the panel stacks on top in a compact two-column grid, the chart comes right under it.

**9.3 Reports**
- Two schedule cards (Weekly summary, Monthly summary): switch, day and time selects, "Send to" checkboxes (Email, In app), hint. View-only roles see everything disabled plus the info notice "Only Corporate Finance & Planners can change schedules or generate reports."
- Header button **Generate report now** (only for roles that may).
- Past reports table: Report, Type, Period covered, Generated, Status (Ready, Generating, Failed), actions View, Download PDF, Try again.
- Preview drawer (560px): summary bullets with citation numbers, key figures table, budget variance (monthly), document activity (weekly), needs attention, sources list, **Download PDF**.

**Charts and numbers rules (all Phase 2 screens)**
- Chart look: thin accent line, hollow points with the last point filled, light gridlines, direct value labels, column and bar charts with the latest bar at full accent and older bars at 35%. One accent plus greys. Max 5 series.
- Every chart has a table view, an accessible text summary and (where marked) image and PDF export.
- On phones charts are drawn at the real width so text stays 11 to 12px. Value labels thin out (every second point) and quarter labels shorten ("Q3 26") when space is tight.
- Values, changes and shares come from the API. The prototype works some out only to fill the sample screens.

**Phase 2 acceptance additions (ADR-0014):** show a badge whenever the API's `display_label` is non-null, with `Updating > Estimated > Draft` precedence — the prototype draws only `Updating` and is not the ceiling. The stale warning appears when any visible chart is stale and a stale chart keeps its figures until interaction or reload; there is no visible refresh control. Empty states are "Figures are being prepared." when `documents_processing` is true, otherwise "No figures yet" with Upload only when `actions.upload` is true. A stale layout save returns the current layout with an inline "layout changed elsewhere" notice, not a modal. The charts page is the detail view: dashboard expansion navigates there with the selected `chart_id`; there is no full-screen expanded chart route, and export buttons stay where the prototype places them. Inline Ask charts are accepted only when the answer response carries a chart payload. Exports use the API metadata and opaque filenames from ADR-0010, not the prototype's title-based filename or `window.print()` PDF.

---

## 10. Later phase direction (do not build in Phase 1 or 2)

**Forecast and scenarios (Phase 3)**
- Scenario picker at the top (Base, Downside, custom), scenario comparison table next to the chart, editable assumptions in a side panel, impact shown instantly. Forecast ranges as a shaded band with a clear "Forecast" label.

**Alerts and risk (Phase 3)**
- Alert list with severity icon plus text, the metric, the threshold and a link to the source. Acknowledge and snooze actions.

**Decisions and approvals (Phase 3)**
- Recommendation card: recommendation, reasoning, confidence level, sources, and an **Approve** button visible only to roles the API allows. A banner if the numbers underneath changed after the recommendation was made.

**Reasoning loops (Phase 3)**
- Hard questions run as queued jobs. Show "Working on it" with a step list and a notification when done. Never block the chat with a long spinner.

---

## 11. Component rules and specs

- One component, one job, one file. Same size limits as `CODING_STANDARDS.md` (about 300 lines per file, about 30 lines per function).
- Presentational components take data through props. They never call the API directly. Fetching lives in hooks or route loaders.
- No business rules in components. Formatting only.
- Every component has loading, empty, error and success states, and a test or story for each.
- Buttons: one primary (near-black) per screen area. Secondary is outlined. Destructive (red text and border, red fill only in confirm dialogs) is used only for delete.
- Badges and pills: icon plus text, never colour only.
- Forms: label above the field, helper text under, error text replaces helper text, required fields marked in words.
- Dialogs: focus trapped, `Esc` closes, focus returns to the trigger.

**Core component list:** `AppShell`, `Sidebar` (collapsible), `MobileTopBar`, `NavDrawer`, `CommandMenu`, `ShortcutsDialog`, `AccessDenied`, `Toast`, `PageHeader`, `Button`, `IconButton`, `Input`, `Select`, `Textarea`, `SegmentedControl`, `Switch`, `Checkbox`, `FileDropzone`, `ProgressBar`, `Badge`, `StatusPill`, `InlineNotice`, `Card`, `Dialog`, `Drawer`, `BottomSheet`, `Popover`, `RowMenu`, `Tooltip`, `DataTable`, `ResponsiveTable` (cards on phones), `EmptyState`, `QuestionBox`, `AnswerBlock`, `StatusLine`, `CitationChip`, `CitationPreview`, `SourcesRow`, `FiguresTable`, `SourcePanel`, `FeedbackBar`, `ThreadList`, `ScopeChip`. Phase 2: `KpiCard`, `Sparkline`, `ChartCard`, `LineChart`, `BarChart`, `HorizontalBarChart`, `VarianceChart`, `SeatTile`.

**Sizes (desktop / 900px and down)**

| Part | Desktop | Phone and small tablet |
|---|---|---|
| Button | 36px high, 16px side padding | 44px |
| Small button | 32px | 40px |
| Icon button | 32px square | 44px square |
| Input and select | 40px, 14px text | 44px, **16px text** (stops iPhone zoom) |
| Segmented control button | 28px | 36px |
| Badge | 22px high, 12px text | same |
| Switch | 36 by 20px (hit area grows by 12px each side on phones) | same |
| Sidebar link | 36px | 44px |
| Citation chip | 24px | 28px |
| Table row (page tables) | 40 to 44px | card layout |
| Drawer width | Documents 440, Dashboard 480, Reports 560 | full width |
| Dialog | max 420 to 440px, width calc(100% - 32px), 24px padding | 16px padding |
| Menu (row actions) | min 180px, radius 12, shadow | rows 12px padding |
| Toast | bottom right | bottom, full width |

**ResponsiveTable (important).** Tables with four or more columns become a list of cards on phones (640px and down):
- Header row hides. Each row becomes a bordered card (radius 8, 12px padding, 8px gap).
- The first cell is the card title (bold, bottom border).
- Every other cell is one line: label on the left (12px muted, from the column header), value on the right.
- A cell with no header text (the actions cell) sits at the bottom right.
- Tables with fewer than four columns, and figure tables inside answers and charts, stay tables and scroll sideways inside their own box (never the page). Their first column stays pinned while scrolling.
- Build this as one component with a column config (`title`, `label`, `hideOnCard`), not as per-page code.

---

## 12. Copy and messages

Plain, calm, short. No jargon, no blame, no exclamation marks, no emoji, no em dashes. Use the curly apostrophe (’) and curly quotes (“ ”) in all text people read.

Approved system messages. Keep every string in one messages file so it can be translated later.

| Situation | Message |
|---|---|
| Database waking (pilot) | "Waking up, please wait." |
| Answer still working | "Still working on your question." |
| Figures being prepared | "Figures are being prepared." |
| Layout saved elsewhere | "The layout changed elsewhere. Check the current layout and save again to reapply." |
| Capacity full or queue wait too long | "We’re busy right now. Please try again in a moment." |
| All models or embedding failed | "Temporarily unavailable. Please try again." |
| No evidence | "I don’t have enough data to answer this." |
| Scan rejected (`scan_reader: none`) | "Scanned files can’t be read in this setup. Please upload a digital file." |
| Low confidence read | "Needs review. Some numbers couldn’t be read with confidence." |
| Partition missing | Show the API message. Fallback: "This company isn’t set up for uploads yet. Please contact your administrator." |
| Duplicate found | "This looks like an existing document. Update it instead?" |
| Permission denied (inline) | "You don’t have access to this." |
| Access denied page | "You don’t have access to this." plus "Your role, {role}, can’t open this page. If you think this is a mistake, ask your administrator." |
| Session ended | "Your session ended. Please sign in again." |
| Wrong sign in details | "That email or password doesn’t match. Check both and try again." |
| Sign in unavailable | "Sign in is temporarily unavailable. Please try again in a few minutes." |
| Stopped answer | "Stopped. Ask again or rephrase." |
| Upload accepted | "Your upload is queued. It will show as Ready when processing finishes." |
| Failed processing | "Processing failed. Please upload the document again." |
| Soft delete done | "Moved to the recycle bin." |
| Restore done | "Document restored to the library." |
| Feedback sent | "Thanks. Your feedback stays in your company." |

Rules:
- Error messages say what happened, then what to do next.
- Button labels are verbs: "Upload document", "Ask", "Try again".
- Use "document" and "source" consistently. Do not mix "file", "doc" and "record" (except in the file picker text).
- Dates and numbers follow the user's locale through `Intl`. Periods display as written in the upload form ("Q3 2026").
- Role names always use the display names: Executive Leadership, Corporate Finance & Planners, Audit & Compliance, System Admin.
- Extract every string in the prototype files into the messages file. Do not retype copy by hand.

---

## 13. Responsive behaviour (full rules)

Every screen works at every width from 320px up. The rules below match the final prototype CSS.

**Breakpoints:** 380, 640, 900, 1180 (and 1280 for the app container). Test widths: 320, 360, 390, 430, 600, 768, 834, 900, 901, 1024, 1180, 1280, 1440, plus a landscape phone (844 by 390).

| Width | What changes |
|---|---|
| 901 and up | Sidebar column (240 or 64). Ask source panel is a column (over 1180) or a floating panel (901 to 1180). |
| 900 and down | One column. Sidebar becomes a drawer with a 48px top bar. Source panel becomes a bottom sheet. Settings gets a sticky tab bar. Buttons, inputs and links grow to 44px. Input text becomes 16px. Citation preview popover is turned off. Dashboard and Settings two-column grids stack. |
| 640 and down | Tables with 4 or more columns become cards. Page padding 16px. Dashboard KPI grid is 2 across. Settings seat tiles 2 across. Charts redraw at the real width. Toasts go full width. Documents bar buttons go full width and the Sort select appears. |
| 380 and down | KPI grid is one column. |

**Always**
- Grid and flex children use `min-width: 0` (and grids use `minmax(0, 1fr)`) so wide content scrolls inside its own box instead of stretching the page.
- Any visually hidden text (`sr-only`) sits inside a positioned parent so it cannot cause sideways page scroll.
- Drawers and sheets that slide in from off screen sit inside a container with `overflow: hidden`.
- Use `100dvh` (with a `100%` fallback) for full-height layouts so phone browser bars do not cut the composer. Add the bottom safe area (`env(safe-area-inset-bottom)`) to the composer, toasts, sheets and drawers.
- Hover-only features (citation preview popover) must have a touch alternative (tap opens the source).
- Sticky headers (Settings tab bar) stay inside the page padding and have a bottom border.
- A mobile app is out of scope for v1. Responsive web is enough.

---

## 14. Accessibility (required, not optional)

- The UI aims for WCAG 2.2 AA, checked by the tests in section 18; no formal conformance is claimed without an audit.
- Every interactive element is reachable and usable with the keyboard, with a visible focus ring (`--focus-ring`, 2px, 2px offset).
- Add a "Skip to main content" link as the first focusable item (not in the prototype, required here).
- Logical heading order. One `h1` per page.
- Streaming answers use an `aria-live="polite"` region so screen readers hear new verified sentences without repeating the whole answer.
- Citation chips, status pills and charts never rely on colour only. Charts have an `aria-label` with the values and a table view.
- Tables use real `<table>` markup with header cells and `scope`. Sortable headers use `aria-sort`. Card layout on phones must keep the same reading order.
- Segmented controls are `radiogroup` or button groups with `aria-pressed`. Switches use `role="switch"` and `aria-checked`. Tabs in the source panel use `role="tablist"`.
- The nav drawer, command menu and dialogs trap focus, close on `Esc` and return focus to the trigger. Background content is inert while a modal is open.
- Respect `prefers-reduced-motion` and browser zoom up to 200%.
- Run `axe` in CI on every screen. A new serious or critical issue fails the build.

Keyboard shortcuts (shown in the help dialog, `?` opens it): `/` focus the question box, `Esc` close panel, menu or dialog, `J` and `K` next and previous citation in the viewer, `Cmd or Ctrl + K` command menu.

---

## 15. Performance targets for the UI

These support the parent latency goals (first streamed response p95 3s, p99 5s, p99.9 7s).

- Render the status line and a two line skeleton within 100ms of sending a question.
- Paint each verified sentence as it arrives. Never wait for the full answer.
- Lazy load the source viewer, charts and `pdf.js`. The Ask screen first load stays small.
- Keep the question box responsive at all times.
- Show "Waking up" only after 2 seconds of waiting, and a "Still working" notice after 8 seconds.
- Largest Contentful Paint under 2.5s on a normal laptop connection for the Ask screen.

---

## 16. Security in the UI

- Every request carries auth. The UI never builds a `company_id` itself. It comes from the authenticated session or the API.
- Never render answer or document HTML directly. Sanitize anything that can contain markup. Document text is data, not instructions and not trusted markup. (The prototype builds screens with template strings and sample data. The real app must escape every value.)
- Source links open through the source viewer API only. Never build links to storage objects in the browser.
- Pre-signed upload links are used once and not stored.
- No sensitive data in URLs, query strings, page titles, analytics events or console logs. Profile photos and previews stay in memory until saved.
- Show the company name and role in the sidebar so users always know which workspace they are in.
- Cached answers show a small "Cached" badge (plan rule). The user can re-run the question.
- Feedback (thumbs) goes to the user's own company only.

---

## 17. What the UI needs from the API

Do not invent fields. If one is missing, stop and ask (section 19). The prototype `can` table in `shell.js` stands in for the first row below.

| Need | Fields (names to agree in the OpenAPI contract) |
|---|---|
| Who am I | name, email, role display name, avatar url, company name, home route |
| What may I do | one flag per capability: ask, view documents, view document contents, upload, update, delete, restore, purge, view dashboard, view charts, view reports, edit report schedules, manage users, view audit log, view cost, approve (later) |
| Documents list | name, category, period, status, version, ingestion state, uploaded by, updated, pages, "may be affected" reason, versions list, failure or review reason, deleted by, deleted at, days until purge |
| Upload form | category list, size limit, allowed types, retention days, duplicate match (id, name, category, period, version), partition ready flag and message |
| Ask | streamed verified sentences, citations (document, version, status, page, table id, excerpt), figures (value as string, currency, units, period, calculated flag, confidence), step status text, cached flag, related questions, scope text, recent questions |
| Source viewer | content blocks (text with highlight range, or table with highlighted cell or row), table title, units, page number and total, newer version flag, availability |
| Settings | profile fields, notification events and values, users, seat limits, MFA policy, audit page, cost data |
| Phase 2 | KPI values and changes (with good or bad direction), series, variance rows, report list and states |

---

## 18. Testing

- Component tests: every component, all four states (loading, empty, error, success).
- Screen tests (Playwright): sign in, upload (new, update, duplicate, partition missing), documents (filter, sort, recycle bin, delete, restore), ask a question, click a citation and see the highlight, stop an answer, insufficient data, busy, waking up, permission denied, settings sections per role.
- Role tests: run the key flows for each of the four roles and check what is visible and hidden.
- Cross-company test: with two test companies, a citation id from company A must never open content for company B (the API blocks it, the UI shows permission denied).
- **Width sweep (new):** open every screen for each role at the test widths in section 13. Fail the build on any sideways page scroll (`scrollWidth` larger than the window width, ignoring elements clipped by `overflow: hidden`), on any console error, or when a tap target on a phone is under 44px (inline citation chips excepted).
- Touch test: emulate a touch phone. Tapping a citation chip opens the sheet (no stuck popover). Closing the sheet by backdrop, button and `Esc` works.
- Accessibility tests with `axe` on every screen and at phone and desktop widths.
- Visual snapshot tests at 390, 768 and 1280 for all nine accepted screens (ADR-0014), compared with the prototype. Approved snapshots are committed under `web/snapshots/` with an `APPROVALS.md` entry naming the approver, date and browser. There is no pixel-difference threshold; a person reviews the visible difference.
- A token-parity test in `web/test/` reads `prototype/styles.css` and fails if the app's colour, type and spacing tokens differ. Tokens come from that one shared file, never hand-copied into components. Allowed differences are listed in ADR-0014: real data replacing samples, standard-wins accessibility, API capabilities, email-only notifications, the pager, MFA, "specified by standard, not drawn" states, absent permission controls and API-driven dashboard/export values.
- Accessibility gate: component `vitest-axe` plus screen `@axe-core/playwright` with zero serious or critical violations; keyboard-only walkthrough per screen; chart table fallback tested with real data so numbers, units and periods read out the same as the chart; explicit contrast checks for chart colours and the evidence highlight; series never distinguished by colour alone.
- One written manual pass per screen with NVDA + Firefox on desktop and VoiceOver + Safari on iOS for the phone sheet, recording tester, date, browser and screen reader so the pass can be repeated after major changes. A serious finding blocks that screen. This is "aims for WCAG 2.2 AA, checked by these tests", not a formal conformance claim.
- Per-role tests assert forbidden controls are absent from the DOM, not merely hidden (§7.6). Citation-click tests require the mounted, authorised source-viewer route (§7.3).
- No real model calls and no real network in unit tests. Use the generated API client with fakes.

---

## 19. Working rules for the coding agent

1. Read this file, `CODING_STANDARDS.md` and `phase1_mvp_plan.md` before starting a UI task. Open the matching prototype file side by side.
2. Plan first: list the screens, components and files you will add, and which API endpoints they use. Ask if unsure.
3. Build in this order: tokens, shell (sidebar, top bar, drawer, command menu, access denied, toast), core components, then screens: Sign in, Documents, Upload, Ask, Source viewer. Settings and Phase 2 screens only after the phase plan says so.
4. Use the generated OpenAPI client. If an endpoint or field you need is missing, stop and ask. Do not invent fields.
5. Match the prototype pixel for pixel on desktop, and behaviour for phone and tablet, using the sizes in section 11 and the rules in section 13.
6. Do not add a library, a font, an icon set or a pattern without saying why.
7. Do not restyle or "clean up" unrelated screens in the same change.
8. When unsure about a value (size, colour, timing, limit), use a token or a config value with a clear name. Never guess inline.
9. Never ship the prototype-only items listed in section 0.
10. After finishing, run the checklist in section 20 and report which items you checked.

---

## 20. UI checklist (use before every pull request)

- [ ] Only tokens used, no raw colours or pixel values
- [ ] Loading, empty, error and success states exist
- [ ] No number is calculated or altered in the UI
- [ ] Every figure has currency, units and period in view (header, subtitle or caption)
- [ ] Every answer shows citations, or a proper "insufficient data" result
- [ ] Citation chip has preview (mouse), tap-to-open (touch), accessible name and opens the exact source place
- [ ] Only approved messages shown, no raw error can reach the user, curly apostrophes used
- [ ] Access is driven by API capabilities, no role names in component logic
- [ ] No sensitive data in logs, URLs, titles or analytics
- [ ] Keyboard use works, focus ring visible, skip link present, `axe` passes
- [ ] Looks and works at 320, 390, 768, 1024 and 1440 widths, no sideways page scroll
- [ ] Phone: 44px targets, 16px input text, tables 4+ columns become cards, sheets and drawers close properly
- [ ] Matches the prototype screen (layout, spacing, order, copy)
- [ ] Text comes from the messages file, not typed inline
- [ ] Tests added: component states, screen flow, role, width sweep and accessibility
- [ ] Both paths of any switch that touches the UI are shown and tested (for example cached answer badge, waking message)

---

## 21. Decisions and defaults (ADR-0014 settles the screen questions)

The prototype and the plan do not fully agree. The decided rows below are binding; the remaining defaults still apply until a later ticket changes them.

| # | Question | Decision or default |
|---|---|---|
| 1 | **Settings screens** (Profile, Notifications, Users, Audit log, Cost view) are in the prototype but not in the Phase 1 UI list in `phase1_mvp_plan.md`. Users, audit and cost are backed by Phase 1 data (roles, audit logs, metering). | **Decided:** all five panes are in Phase 2 acceptance with the prototype's role visibility; unknown section falls back to Profile (ADR-0014). |
| 2 | **Dashboard, Charts, Reports** are Phase 2 (and scheduled reports may be Phase 3). Executive Leadership lands on Dashboard in the prototype. | **Decided:** Dashboard and Charts are accepted in Phase 2; Reports is design reference only and its final placement is with #360. Phase 1 keeps Executive Leadership on Ask (ADR-0014). |
| 3 | **Inline chart inside an Ask answer** appears in the prototype. Charts are Phase 2 in the plan. | **Decided:** accepted in Phase 2 only when the answer response carries a chart payload; the client never invents one (ADR-0014). |
| 4 | **Delete from Upload.** The plan and `upload_types` list New, Update, Delete. The prototype upload form shows only New and Update and does Delete from Documents. | Keep API `upload_type: delete`. UI offers Delete from the Documents drawer only. |
| 5 | **Delete permanently** (early purge from the recycle bin) is not in D5, which keeps soft deletes for the retention period. | **Decided:** keep Delete permanently with the prototype's dialog and toast, for upload-capable roles only and with backend enforcement before the button renders; System Admin is denied (ADR-0014). |
| 6 | **Permissions matrix** needs extra actions the UI uses: view documents list, view document contents, view dashboard, view charts, view reports, edit report schedules, view cost, manage users. | **Decided in ADR-0012:** add only `dashboard_view`, `dashboard_edit_layout`, `chart_export`, `kpi_view`, `kpi_export`; KPIs are not a category and #359/#360 own the enum and matrix updates. |
| 7 | **Notification events and Push channel.** The sample list includes "Mentions" (no such feature) and Push (needs a service worker, no mobile app in v1). | **Decided:** email only with API-driven events; remove the Push column and "Mentions" as an approved difference from the prototype (ADR-0014). |
| 8 | **Number format.** v1 said thin-space separators, the prototype uses en-US commas. | Use `Intl` with en-US now. Revisit per company locale later. |
| 9 | **Cached badge, newer version banner, "Open full document", source not available state, citation `1/3` paging** are required by this file but not drawn in the prototype. | **Decided:** build them from the descriptions in section 7, mark them "specified by standard, not drawn", and sign off their snapshots; no prototype visual is added. Unavailable and no access share one non-leaking screen (ADR-0014). |
| 10 | **Metric hover** showing the inputs of a calculated figure. | Tag only for now. |

---

## 22. Research sources used for this document

Reviewed during design research. Visual details of private products were not inspected directly, so treat them as direction, not exact specs.

- Hebbia: citation previews that show source data without breaking flow, source linked answers.
- AlphaSense: generative search side panel, inline citations that open the document viewer with the passage highlighted, related questions.
- Perplexity (UX teardowns): numbered inline citations, sources row, chip popovers with paging, "Wrong sources" feedback.
- Ramp (public design system extractions): white canvas, near-black text, single accent, Inter, 4px grid, outline icons.
- Mosaic, Runway, Pigment (public product pages and reviews): KPI cards, scenario comparison tables, variance first dashboards.
- General AI UX citation pattern guidance: use both inline chips and a sources panel, avoid anonymous markers without publisher identity.
- The final FinSight AI HTML prototype (12 files), reviewed and tested at 13 screen widths.
