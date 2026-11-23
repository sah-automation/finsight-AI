# FinSight AI UI prototype

This folder is the user-supplied, binding UI source for issue #349 and its parent #345. It is the visual contract for the frontend: match the layout, tokens, copy, states and interaction order. Do not redesign or replace it when building the real screens.

## Open and view

- There is no build step required: open `login.html` directly in a current desktop or mobile browser, for example `file:///path/to/repo/prototype/login.html`.
- Keep the folder together. Each HTML file is standalone and loads only the local relative assets `styles.css`, `shell.js` and (where needed) `charts.js`.
- Start at `login.html`. Choose a role with the prototype-only **Sign in as** selector, then sign in. Use **Preview as** in the sidebar and the prototype-only **State** selector on Ask/Dashboard to inspect variants.
- There is no server, package install, API or network access involved. All data is sample data.

## Files and conventions

| File | Purpose |
|---|---|
| `styles.css` | Shared tokens (colours, 4px spacing scale, Inter-first typography, radii, focus ring) and reusable components. |
| `shell.js` | Shared sidebar, phone menu, command menu, shortcut help, role preview and access-deny content. |
| `charts.js` | Small SVG chart helpers used by the chart-bearing screens. The real app computes values in code and sends them from the API. |
| `login.html`, `ask.html`, `documents.html`, `upload.html`, `dashboard.html`, `charts.html` | Screens named in the original #349 acceptance list. |
| `settings.html`, `reports.html`, `not-allowed.html` | User-added screens retained in the binding source; see below. |

Prototype-only controls are deliberately visible so states can be reviewed: role preview, sign-in-as, State selectors, sample data labels and login state links. They must not appear in the product. `sessionStorage`/`localStorage` are used only to remember the preview role and sidebar preference. Numbers worked out by the prototype scripts are illustrative; the product displays API values.

## User-added screens

The original #349 list covered sign-in, Ask, Documents/recycle bin, Upload, Settings, Dashboard and Charts. The user also supplied:

- `reports.html` — scheduled report cards, report configuration and a preview/download drawer. Scheduled reports belong to a later phase; the file is design reference only.
- `not-allowed.html` — shared access-denied state for a role that cannot open a route.
- `settings.html` is expanded into five sections rather than a single page: Profile, Notifications, Users, Audit log and Cost view.

These additions are already reflected in `UI_STANDARDS.md` section 6 (screen inventory and phases) and section 21 (open decisions). No phase scope changes with this delivery.

## Component states

| State | Where to inspect it |
|---|---|
| Loading | Ask **Working** and **Waking up** states; Dashboard **Loading** state; Upload progress and "Checking file". |
| Error | Login `#wrong` and `#down` states; Ask **Busy**, **Unavailable** and **Permission denied**; Documents failed ingestion; Upload duplicate warning. |
| Empty | Ask new conversation; Documents empty recycle bin and no matches; Dashboard "No figures yet". |
| Disabled | Login while unavailable; Settings **Save changes** until edited, full-role options and unavailable menu actions; Reports controls in read-only mode. |

Toasts, alerts, live regions and retry affordances are included alongside these states.

## Accessibility and focus order

ARIA roles, labels and live regions are annotated in the HTML. Each screen also has an `Accessibility: focus order` comment beside `<body>`; the intended order is:

- `login.html`: work email, password, forgot-password link, sign in/retry, then prototype controls.
- `ask.html`: sidebar, question box, send, answer/citations, source viewer, then command menu/help overlays.
- `documents.html`: sidebar, view switcher, search/filters, table, row actions, details drawer or confirm dialog.
- `upload.html`: sidebar, upload type and fields, drop zone, file actions and submit; disabled/error states keep the same order.
- `dashboard.html`: sidebar, filters, KPI cards, detail drawer; state selector is prototype-only.
- `charts.html`: sidebar, chart type, data fields, output and save actions.
- `reports.html`: sidebar, schedule switches, report fields, history, preview drawer and download.
- `settings.html`: sidebar, section tabs, active pane fields/actions, then dialog or action menu.
- `not-allowed.html`: sidebar, home-route link, then Go back.

`Esc` closes panels, menus and dialogs and returns focus to the trigger. `Cmd/Ctrl + K` opens the command menu, `?` opens shortcut help, `/` focuses the Ask question box, and `J`/`K` moves through source citations. The real frontend still adds the skip link and formal focus trapping required by `UI_STANDARDS.md` section 14.

## Relationship to the standards

`UI_STANDARDS.md` is the behavioural and implementation rulebook; this folder decides appearance and interaction order. Parent #345 declares this root `prototype/` directory the binding source. Any mismatch between a plan and these files is recorded in `docs/plans/phase1/phase1_as_built_deviations.md` rather than silently redesigned here.
