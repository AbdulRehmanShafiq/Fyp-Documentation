# VousFin Frontend — Complete Redesign Master Spec ("Ledger")

- **Date:** 2026-07-14
- **Status:** Draft for user review (planning only — no code in this pass)
- **Scope:** `vousfin-frontend-main/` — React 19 + Vite SPA (119 page components, ~108 shared components)
- **Supersedes / absorbs:** `2026-06-24-vousfin-frontend-redesign-design.md` (IA + nav — **kept**, refined), `2026-07-03-vousfin-minimal-redesign.md` (calm minimalism — **kept as the design temperament**, its unfinished phases folded in here), the mobile-first and easy-daily-loop passes (**kept**, generalized).
- **Method:** full codebase audit (routes, nav config, tokens, primitives, page patterns, measured duplication counts) → principle extraction from Stripe / Linear / Mercury / Ramp / Notion / Carbon / Fiori / HIG / Material 3 / Radix / QuickBooks / Xero / NetSuite → three strategy options weighed → this blueprint. Multiple self-review passes applied before finalizing.

---

## 0. The one-paragraph thesis

VousFin's *bones* are right — the 6+3 module IA, the rail+panel navigation, the ⌘K command bar, the CSS-variable token engine, the TanStack Query data layer. What is wrong is everything layered on top of those bones: **five accreted design languages** (Nocturne Ledger → premium glass/grain → 5 themes → calm density → easy-mode) coexisting with **no governance**, so every screen looks like the era it was last touched in. The redesign is therefore not another coat of paint and not a rewrite. It is the **installation of a single, opinionated design language ("Ledger") delivered through a governed component library that every one of the 119 pages is migrated onto** — plus the workflow surfaces (unified work views, global report period, close cockpit, keyboard-first actions) that make VousFin feel like an accountant's operating system instead of a collection of pages.

---

## 1. Current Frontend Audit (measured, not impressionistic)

### 1.1 What exists

| Layer | State |
|---|---|
| Routing | 119 page components, all lazy + ErrorBoundary + Suspense (`routes.jsx`). Legacy redirects preserved. |
| IA / Nav | 6 always-on + 3 enableable modules + Settings in `nav.config.js` (single source of truth). Hybrid 64px rail + 216px contextual panel (`RailPanel.jsx`), collapsible, module enablement via `useModulesStore`. |
| Header | Title (derived from nav config) + ⌘K trigger + bell (plain link to `/activity`) + profile menu. No breadcrumbs, no business switcher, no notification center, no global period. |
| Command bar | 4 shipped phases: client catalog → semantic catalog → grounded how-to AI → analytics. Genuinely differentiating. |
| Theming | CSS `--c-*` channel engine; **5 themes** (Atelier default, Eclipse, Terminal, Maison, Daybreak) × **2 densities** (calm/cozy) = 10 visual matrices. Per-theme radius AND display font (Playfair/Fraunces serif in-app on 2 themes). |
| Tokens | Semantic layer exists (`status.*`, `positive/negative`, `text.*`, type-scale vars) **but the legacy palette vocabulary dominates**: `navy/charcoal/cyan/gold/amber/emerald` all alias theme vars. |
| Motion | CSS keyframe zoo (`fade-in`, `rise-in`, `collapse-down`, `chart-enter`, `value-glow`, `stagger-rise`…) + framer-motion imported in only **7 files**. Global reduced-motion guard exists (good). |
| Mobile | Purpose-built kit (`Sheet`, `ListCard`, `SwipeRow`, `PullToRefresh`, `MobilePage`) + `useIsMobile()` render-forks in **7 pages**. The other ~90 app pages fall back to `responsive-rows` auto-stacking or horizontal scroll. |
| i18n | Scaffold only: `en.json` = 229 lines; ~all page copy is hardcoded English literals. Urdu promise unmet beyond nav + a few pages. |
| Tests | ~64 Vitest files (command bar, mobile kit, utils) — logic-heavy, almost no visual/behavioral coverage of pages. |
| Print | Real print stylesheet flipping tokens to ink-on-paper (good, rare). |

### 1.2 Measured design debt (the numbers that justify "complete", not "tweak")

| Finding | Measurement |
|---|---|
| Arbitrary font sizes (`text-[11px]`…`text-[15px]`) | **976 occurrences across 126 files** — despite a type-scale token layer existing since June |
| Legacy palette classes (`text-cyan/gold/amber/emerald*`) | **646 occurrences across 147 files** — `text-cyan` renders *gold* on Atelier; the class names lie |
| Table systems | **3 competing systems**: raw `<table>` in 37 files, `DataTable` in 10, `QuietTable` in 2 (+ `responsive-rows` CSS hack for mobile) |
| Button / Input primitives | 2 Buttons, 2 Inputs, `Select` + `SelectField`, 2 export buttons — `common/*` still imported by 4 files |
| `PageHeader` adoption | **3 of ~90 app pages** |
| God components | `TransactionFormModal.jsx` **2,256 lines**; `AdminPage` 1,353; `AIForecastPage` 991; `BankReconciliationPage` 872 |
| Reports hub | **All 10 report tabs eager-mount on entry** (10 parallel fetch trees); each tab re-implements its own date range — no global period |
| Dead code | `SectionRail.jsx` (unimported), `SectionHubPage.jsx` (superseded by `ModuleCommandCenter`), legacy nav aliases (`RAIL_ITEMS`, `HUB_SECTIONS`, `NAV_SECTIONS`) |
| Virtualization | None (no react-window / tanstack-virtual) — ledgers/GL render every row |
| Overlay cost | Film-grain overlay is a **fixed, full-screen, `z-60`, `mix-blend-overlay`** element painted *above all content* on every frame, on every theme |

### 1.3 What is genuinely excellent (protected — the redesign builds on these)

1. **The IA** — 6+3+Settings with dual plain/accounting labels. It matches how owners *and* accountants think. Do not reopen this.
2. **Rail + contextual panel** — 1 click to anywhere; collapsible; module enablement. Keep the model, refine the skin.
3. **⌘K command bar** — search + navigate + grounded AI how-to. This is the discoverability spine; the redesign promotes it further.
4. **The CSS-variable engine** — the delivery mechanism for the new token system already exists. We change *values and vocabulary*, not the mechanism.
5. **`.num` tabular mono figures, print stylesheet, global reduced-motion guard, focus-ring utility.**
6. **Data layer** — TanStack Query (5-min staleTime), Zustand stores, single Axios instance, `getErrorMessage()`. Untouched.
7. **The mobile kit components** (Sheet/ListCard/SwipeRow/PullToRefresh) — kept, but re-positioned as *responsive* primitives instead of fork-only ones (§10.3).
8. **Plain-language copy principle** and smart transaction entry (NL parsing + simple mode).
9. **Per-page lazy + ErrorBoundary discipline**, chunk-reload recovery in `routes.jsx`.

---

## 2. Major UX/UI Problems (ranked by user pain × engineering drag)

**P1 — No single design language.** Five eras coexist. A user moving Dashboard → Invoices → Reconciliation → Tax crosses three visual dialects (calm hairlines, premium glass cards, dense bespoke tables). Trust is the product in accounting software; visual inconsistency reads as unreliability.

**P2 — The token vocabulary lies.** 646 usages of color classes named for hues they no longer render. New code copies old code, so entropy compounds. There is no lint rule preventing `text-[13px]` or `text-gold`, so the 976-instance type zoo regrows even after a cleanup.

**P3 — Three table systems and no workhorse.** Accounting software *is* tables. VousFin has no canonical data grid: no saved views, no bulk actions, no column control, no keyboard navigation, no virtualization, no consistent money alignment. Every list page hand-rolls filters and empty states.

**P4 — Workflows end at page boundaries.** Recording a payment against an invoice, chasing an overdue balance, accepting an AI match — each requires page hops. Inline actions (the June spec's Phase 7) never shipped. Month-end close — the accountant's most important recurring ritual — has no surface at all.

**P5 — Reports are ten silos.** No shared period (set P&L to "last quarter", switch to Balance Sheet, lose it), all ten eagerly fetch, statement typography is flat (a subtotal looks like a line item), and numbers are dead ends — no drill-through to the GL.

**P6 — Mobile is a fork, not a property.** 7 hand-built mobile twins; the other ~90 pages degrade. The fork pattern cannot scale to 119 pages and doubles maintenance forever.

**P7 — Enterprise table stakes missing.** No business switcher (accountant-with-clients), no real notification center (bell is a link), no saved views, no keyboard shortcut system beyond ⌘K, no user-visible audit "who changed this" affordance at field level.

**P8 — The 10-matrix theme surface is unQAable.** 5 themes × 2 densities × print × mobile. Every new component must be eyeballed 10+ ways or (in practice) 1 way — so 9 combinations silently rot. Two themes carry serif display fonts into a data UI, hurting number-dense screens.

**P9 — God components block iteration.** The 2,256-line universal create modal is where entry UX goes to calcify; editors (invoice 634, PO 717, bill 538) triplicate one document pattern.

**P10 — i18n and a11y are scaffolds.** Copy is hardcoded (blocks Urdu/RTL); a11y is good at the utility level (focus ring, reduced motion) but unenforced at the component level (icon-only buttons, table `scope`, color-only status, muted-text contrast on dark themes).

---

## 3. Redesign Strategy — three options weighed

| | A. Restyle in place | **B. Systemic rebuild on existing bones (chosen)** | C. Greenfield shell (TS + shadcn, new app) |
|---|---|---|---|
| What | New tokens + polish sweep | One design language + governed component library + workflow surfaces; migrate all 119 pages onto it in waves | New repo/shell, port pages |
| Fixes P1–P3 | Cosmetically, regrows | Structurally (lint-enforced) | Structurally |
| Fixes P4–P7 (workflows) | No | Yes — new surfaces are the point | Yes, eventually |
| Risk to a live accounting product | Low | Medium, phase-gated, each wave shippable | High (long freeze, regression risk on 119 pages, retest everything) |
| Cost | S | L | XXL |
| Verdict | Rejected — this is the "tweak plan" the user explicitly refused | **Chosen** | Rejected — the bones are good; rewriting them buys nothing users can feel |

**Chosen strategy (B), stated precisely:** keep routing, data layer, IA, nav model, command bar. Build `src/design-system/` — tokens v2, motion system, ~28 governed components — with **ESLint enforcement that makes the old vocabulary un-writable**. Migrate pages in module-sized waves, deleting the superseded primitives behind each wave. In parallel, ship the five workflow surfaces (App Shell v2, Work View, Reports v2, Document Editor v2, Today/Close). "Complete redesign" = by the final wave, **no screen is left un-migrated and every legacy primitive is deleted** — the tweak-trap is avoided by the deletion gates, not by ambition statements.

---

## 4. The Design Language — "Ledger"

*(Aesthetic direction per the frontend-design discipline: deliberate, subject-grounded, one signature risk.)*

### 4.1 Concept

The subject's own world is the double-entry ledger: ruled paper, tabular figures, ink hierarchy, the quiet authority of a bound book of record. **Ledger** is that heritage rendered as a modern fintech instrument — *"a private bank's book of record, opened on a screen."* It resolves the current identity crisis (luxury-gold landing vs 5-dialect app) by making the app the **calm, precise interior** of the brand whose **expressive exterior** is the landing page.

**Temperament (from the calm program, kept):** quiet, confident, mostly empty until needed. Whitespace and hairlines do the work of boxes. One accent, used rarely.

### 4.2 The four moves

1. **Ink on paper, inverted.** Two first-class modes derived from ONE semantic palette: **Ledger Dark** (evolution of Atelier: warm near-black `#131110` canvas, cream ink, champagne accent used *only* for primary action + active nav) and **Ledger Light** (evolution of Daybreak, re-hued to the same warm-neutral family so dark/light feel like one brand, not two themes). Money keeps its own semantic pair — jade in / clay out — never the accent.
2. **Figures are the typography event.** Numbers are the protagonist: `Spline Sans Mono` tabular figures everywhere money appears, sized *up* relative to labels, with a strict money-emphasis scale (hero / total / subtotal / line). UI text stays `Schibsted Grotesk`. **Serif display fonts leave the app** (they remain the landing's voice) — data screens earn trust through precision, not flourish.
3. **The rule is the signature.** The horizontal hairline — the ledger's ruled line — becomes the one structural motif: section dividers, table rows, statement subtotals (single rule) and totals (double rule, exactly like a hand-ruled ledger). *This is the aesthetic risk:* statement tables and totals app-wide adopt real ledger ruling (single-rule above subtotal, double-rule above grand total) instead of boxes and background fills. It is distinctive, subject-true, and it costs nothing in accessibility.
4. **Atmosphere retreats to the edges.** The aurora stays only on Home, auth, and empty states at reduced strength. The z-60 film grain overlay is **removed from data surfaces entirely** (kept, faint, on the landing page only). Depth on dark comes from borders and layered surface tones, not shadows and blend modes.

### 4.3 Principles extracted from research (what we take, not copy)

| Source | Principle taken into Ledger |
|---|---|
| Stripe Dashboard | Restrained hue count; density with clear hierarchy; every number drillable |
| Linear | Speed *is* design; keyboard-first; one theme executed perfectly beats five executed partially |
| Mercury | Calm dark luxury for finance is viable — through space and type, not effects |
| Ramp | The product's job is to *finish workflows*, so actions live inline where data lives |
| Notion | Progressive disclosure — simple surface, power one click deeper (matches easy-mode program) |
| IBM Carbon | Data-table spec rigor: row heights, alignment rules, batch actions, skeleton states |
| SAP Fiori | Shell concept: global shell owns search/notifications/switcher; workspaces own content |
| Apple HIG | Deference — chrome recedes, content (numbers) leads; motion as feedback |
| Material 3 | Token architecture: reference → system → component tokens (we adopt the 3-layer model) |
| Radix/shadcn | Headless, owned components with a11y built in — adopt primitives selectively (§8.4) |
| QuickBooks/Xero | Accounting IA conventions (validated our 6+3), global "+ New", business switcher expectations |
| NetSuite | The anti-pattern: density without hierarchy, configuration without opinion. What Ledger must never become |

---

## 5. Proposed Information Architecture

**The 6+3+Settings module model is kept** (locked 2026-06-24, live in `nav.config.js`, validated against QBO/Xero). Refinements only:

1. **Home becomes "Today".** The Command Center inbox is *merged into* Home (not a sub-item) — one landing surface: answer → inbox → shortcuts. `/command-center` remains as the "expanded inbox" deep view. Rationale: two "start here" surfaces compete for the same job today.
2. **Transactions gets two named lenses, one page.** Today `/transactions` appears under both Banking ("Money movements") and Accounting ("Journal"). Make this explicit: one page, `?lens=money|journal` — Banking opens the plain money view (in/out, running cash), Accounting opens the journal lens (debit/credit columns, JE numbers, compound-entry expansion). Same data, two vocabularies — the dual-label IA principle applied to a page.
3. **Accounting gains "Close"** (primary item): the month-end close cockpit (§7.5, roadmap Phase 9) — checklist of unreconciled items, pending approvals, drift check, draft statements, lock period. This is the accountant's ritual with no home today.
4. **Reports absorbs nothing new but gains the global Period context** (§12.3).
5. **Settings gains "Modules"** (exists in `ModulesCard` — promote to a named item) and, on the roadmap, **"Organizations"** for the multi-business switcher.
6. Everything else stays where the June spec put it. The complete page→module mapping in that spec remains authoritative.

**Naming stays dual-label** (plain word primary, accounting term as `tag`) — this is working and matches the product-copy memory rule.

---

## 6. Navigation Hierarchy — App Shell v2

The shell is where enterprise credibility is won. Keep the model; upgrade the chrome:

```
┌──┬──────────────┬──────────────────────────────────────────────┐
│64│ Contextual    │ Header: [breadcrumb ▸ deep routes only]      │
│px│ panel (216px, │   [Period ⌄ · reports/planning surfaces]     │
│  │ collapsible)  │   [⌘K Search]  [🔔 Notifications]  [Org ⌄]   │
│R │               ├──────────────────────────────────────────────┤
│A │  MODULE       │                                              │
│I │  • item       │           Content workspace                  │
│L │  • item       │                                              │
│  │  ────────     │                                              │
│⚙ │  grouped      │                                              │
└──┴──────────────┴──────────────────────────────────────────────┘
```

- **Rail (keep, calm-skin):** monochrome at rest; active = 2px accent bar + tinted icon (already close). Module accents remain identity-only. Grouping hairlines between {Today}, {Sales·Purchases·Banking}, {Accounting·Reports}, {enabled extras}, {Settings} so nine icons parse as four zones.
- **Panel (keep):** adds tiny live badges from a single shared poller (approvals count exists; extend pattern). Item descriptions (already in nav.config `desc`) surface as tooltips.
- **Header v2 (rebuild):**
  - *Breadcrumbs only on deep routes* (detail/editor pages) — top-level pages show the plain title (current behavior, kept).
  - **Global Period control** appears contextually on Reports/Planning surfaces (§12.3).
  - **Notification center**: bell opens a popover inbox (approvals waiting, AI queue items, failed jobs, close-deadline warnings) fed by existing queues — *not* a new backend; it aggregates counts the app already polls. Deep-links into the owning surface.
  - **Organization switcher** (roadmap slot, right of profile): design the affordance now, ship when multi-business lands. Displays business name + avatar; the menu lists orgs + "Manage".
  - **+ New** global create button (universal create is currently only in the mobile bottom bar and dashboard actions — desktop deserves the QBO-style omnipresent create).
- **Mobile:** bottom bar stays (Home · module · ⊕ · AI · Menu). The menu sheet is regenerated from `nav.config` (single source, kills drift with `MobileMenuSheet`).
- **Keyboard spine:** ⌘K (exists) + a **global shortcut map**: `g` then `s/p/b/a/r/t` = go to module; `c` = create; `/` = search; `?` = shortcut overlay; `j/k` + `x` + `Enter` in all work views (§7.2). Shortcuts render in tooltips and the ⌘K footer — Linear's discoverability pattern.

---

## 7. Workspace & Workflow Redesign

Five reusable *surface types* replace per-page invention. Every routed page becomes an instance of one of these (or a Settings form):

### 7.1 Today (Home)
See §11 (Dashboard strategy).

### 7.2 Work View — the universal list-and-act surface
One pattern for Invoices, Bills, Customers, Vendors, Transactions, POs, GRNs, Approvals, Review Queue, Exceptions, Assets, Employees, Inventory:

```
PageHeader:  Title + count · primary action (one filled button) · overflow
FilterBar:   [Search] [Status ⌄] [Date ⌄] [+ Filter]      [Saved views ⌄] [Columns ⌄]
SmartTable:  virtualized rows · money right/tabular · status chips ·
             hover row-actions · checkbox select → BulkBar slides in
Detail:      row click → right-side Inspector panel (split view) on ≥xl,
             route push on smaller screens — list context never lost
```

- **Saved views** (per user, localStorage first, server later): "Overdue > 30d", "Awaiting my approval". The FilterBar serializes to the URL so views are shareable.
- **Inspector** (split view) kills the biggest click tax: peek at an invoice, record a payment, jump to full editor only when editing lines.
- **Bulk actions**: approve/send-reminder/export/categorize on selection — the Ramp lesson.
- **Keyboard:** `j/k` move, `x` select, `Enter` open, `e` primary action, `.` action menu.

### 7.3 Document Editor — one scaffold for Invoice/Bill/PO/Credit notes
Today three ~600-line editors triplicate one pattern. One `DocumentEditor` scaffold:
- Header: party picker + dates + reference; status chip; sticky **TotalsPanel** (subtotal → tax → total, live).
- **Line grid**: keyboard-first (Tab/Enter navigate, auto-add row), item/account combobox with inline create, per-line tax preview (`TaxPreviewPanel` exists — standardize).
- Sticky action bar: one filled primary (Save/Send), ghost secondaries; dirty-guard; ⌘Enter save.
- Right rail (≥xl): AccountingImpactPanel (exists), activity timeline (exists), AI check ("this bill looks 12% above this vendor's usual" — hooks into anomaly service).
- The **2,256-line `TransactionFormModal` is decomposed** onto the same Field/line-grid primitives: Simple mode (chips + NL) stays the front; Detailed mode becomes a thin composition instead of a monolith. Entry pipeline/API contracts untouched (answer-literal contract respected).

### 7.4 Match View — reconciliation & review queues
Bank reconciliation, AI review queue, exceptions: one two-pane match surface — external evidence left, book candidates right, confidence-ranked suggestions center, `a` accept / `s` skip / `m` manual-match keys, bulk-accept above threshold. Progress bar ("34 of 120 matched") for the session feel.

### 7.5 Close Cockpit (new, Accounting → Close)
The month-end ritual as a surface: a period checklist — bank rec status per account, unapproved journals, AI queue empty?, AR/AP control reconciliation (backend integrity gate exists), draft statements preview, anomaly sweep, then **Lock period** (uses existing fiscal-year machinery). Each line deep-links to the surface that clears it. This is the single highest-leverage *new* accountant feature the frontend can ship on existing APIs.

### 7.6 Cross-cutting workflow rules
- **Inline first**: record payment, send reminder, approve, void — available from list rows and inspector without leaving context.
- **Action naming carries through**: the button that says "Send invoice" produces the toast "Invoice sent" (copy system, §13).
- **Optimistic + undoable** where the ledger allows (UI-level undo = reversal entry offer, never mutation of history — accounting rules respected).
- **Every AI suggestion is explainable**: confidence + "why" + one-keystroke accept/reject, consistent across review queue, classification, matching (AI philosophy: assist, never invent).

---

## 8. Design System Specification

Three-layer token architecture (Material 3 model) on the existing CSS-variable engine. **Vocabulary is new; the mechanism is not.**

### 8.1 Color tokens (semantic layer — components may reference ONLY these)

```
surface/   canvas · raised · overlay · sunken · inverse
ink/       primary · secondary · tertiary · disabled · on-accent · on-status
accent/    default · hover · subtle (8-12% tint) · border
money/     in · in-subtle · out · out-subtle · neutral
status/    success · warning · danger · info  (+ -subtle fills for chips)
border/    hairline · strong · focus
chart/     c1…c8 (categorical, colorblind-safe) · grid · axis
           + semantic: revenue · expense · profit · cash · forecast(dashed)
```

- Backed by the `--c-*` channels; **Ledger Dark** and **Ledger Light** are the two first-class value sets (§4.2). Existing Atelier/Daybreak values are the starting points, re-tuned for AA contrast (every `ink/*`-on-`surface/*` pair ≥ 4.5:1; `ink/tertiary` today fails on some dark surfaces — fix at the token, not per page).
- Legacy names (`navy/cyan/gold/amber/emerald/glass…`) survive as deprecated aliases during migration and are **deleted at each wave's gate** (§16).
- Money colors are *never* used for status, accents *never* for money — chips + icons accompany color so state is never color-only.

### 8.2 Typography

| Role | Face | Size/weight (desktop) | Use |
|---|---|---|---|
| `display` | Schibsted Grotesk 600 | 32/1.1 | Hero answers (Today, module centers) |
| `title` | Schibsted Grotesk 600 | 20/1.3 | Page titles |
| `heading` | Schibsted Grotesk 600 | 16/1.4 | Section headers |
| `body` | Schibsted Grotesk 400/500 | 14/1.55 | Default |
| `small` | Schibsted Grotesk 400 | 13/1.5 | Secondary cells, help |
| `label` | Schibsted Grotesk 500, +0.04em caps | 11 | Eyebrows, column headers |
| `money-hero` | Spline Sans Mono 600, tabular | 30 | The one number |
| `money-total` | Spline Sans Mono 600 | 16 | Statement totals |
| `money` | Spline Sans Mono 500 | 14 | Cells, rows |

Rules: the full scale is registered in Tailwind `fontSize` **and arbitrary `text-[Npx]` is lint-banned**; mobile body floor = 16px inside mobile surfaces; serif never appears inside the app shell.

### 8.3 Space, radius, elevation, iconography

- **Space:** 4px grid, `space-1..12`; page gutter 32 (24 on md, 20 on mobile); section gap 28; card padding 20. **One density** — the calm/cozy toggle is retired; calm's values are *the* values (one less matrix, per Linear's lesson).
- **Radius:** fixed 3-stop — control 8 / card 12 / overlay 16. No longer a theme personality knob (a per-theme radius means no component ever looks "designed"; it looks parameterized).
- **Elevation:** dark = surface-tone steps + hairlines (shadows barely read on near-black); light = 3 shadow levels (card/raised/overlay). Glass/backdrop-blur reserved for overlays (menus, command bar) only.
- **Icons:** Lucide only, sizes 16/18/24, stroke 1.75, always with `aria-label` when standalone. No emoji as UI icons.
- **Ledger ruling (signature):** subtotal rows carry a single top rule (`border/strong`), grand totals a double rule — implemented once in `StatementTable` and `TotalsPanel`.

### 8.4 Component primitives — build vs adopt

Adopt **Radix UI primitives** (Dialog, Popover, DropdownMenu, Tooltip, Tabs, Switch, Checkbox — headless, WAI-ARIA complete, React-19 safe) and skin them with Ledger tokens; hand-roll what Radix doesn't give (SmartTable, PeriodPicker, money inputs). Rationale: hand-rolled a11y across ~28 components is the single biggest hidden cost of option B; Radix removes it for ~40kB. *(Open decision #3 if the user prefers zero new deps.)*

### 8.5 Motion system (framer-motion as the one engine)

Tokens: `duration/fast 140ms · base 200ms · slow 300ms`; `ease/out [0.16,1,0.3,1]` (entrances), `ease/inout [0.4,0,0.2,1]` (state), spring `{stiffness 400, damping 30}` (touch/gesture). Choreography rules:

1. Page enter: fade + 8px rise, once; never re-animate on refetch.
2. Lists: 30ms stagger on first paint only.
3. Overlays: fade+scale 0.98→1 (`AnimatePresence`); sheets slide with spring.
4. Numbers: count-up on *hero* figures only, once per mount.
5. Hover: color/border/opacity only — no layout-shifting scale.
6. One signature moment: rail→panel shared-axis slide (kept from June spec).
7. Everything through a `motion/` module exporting shared variants; CSS keyframe animations deleted as pages migrate; `useReducedMotion` → opacity-only fallback (top-level guard already exists).

### 8.6 Charts (Recharts standard, dataviz-principled)

One `ChartFrame` wrapper: token-fed colors (`chart/*`), hairline grid (y only), no legend when ≤2 series (label lines directly), tabular-figure tooltips, forecast = dashed + confidence band, sparklines for dashboard, every chart offers a data-table alternative (a11y), empty/loading/error states built in. Kill per-chart bespoke gradients.

### 8.7 Copy system

Plain-language-first (established memory rule) becomes enforceable: all *new/migrated* surface copy goes through i18n keys (`en.json` domains per module), sentence case, verbs on buttons ("Send invoice", never "Submit"), errors = what happened + how to fix, empty states = one line + one action. Urdu fills per module wave (RTL already scaffolded).

---

## 9. Component Library Strategy

### 9.1 Structure

```
src/design-system/
  tokens/        css vars + tailwind preset (single source)
  motion/        variants, transitions, hooks
  primitives/    Button IconButton Field Input MoneyInput Select Combobox
                 DatePicker Checkbox Switch TextArea Badge StatusChip
                 Tooltip Kbd Avatar Money Delta
  containers/    Card Sheet(=modal/drawer/bottom-sheet, one component)
                 Menu Tabs Section PageHeader EmptyState Skeleton Toast
  data/          SmartTable StatementTable KPI Sparkline ChartFrame
                 Timeline InboxList FilterBar BulkBar
  workflow/      SplitView Inspector PeriodPicker ApprovalBar AIExplain
                 DocumentEditor(scaffold) MatchView(scaffold)
```

~28 components. Each ships with: prop-typed API, a11y behavior (from Radix where adopted), loading/empty/error states where applicable, Vitest behavioral tests, and a catalog entry.

### 9.2 Governance (what makes this migration stick when two prior ones didn't)

1. **Living catalog** at `/design` (dev-only route): every component, every state, both modes — the cheap Storybook. Doubles as the FYP demo of the design system.
2. **ESLint gates** (custom rules + `eslint-plugin-tailwindcss`): ban arbitrary `text-[Npx]`, ban legacy palette classes, ban raw `<table>` outside `data/`, ban `framer-motion` imports outside `motion/` consumers, ban new `components/common/*` imports. Rules land **warning-level globally, error-level on migrated waves** (ratchet).
3. **Deletion gates:** a wave is "done" only when the superseded primitive/file is deleted (`DataTable`, `QuietTable`, `common/Button`, `common/Input`, `SectionRail`, `SectionHubPage`, `responsive-rows`, keyframe zoo…). No deletion, no done.
4. **Drift guard tests** (pattern exists for command-bar catalog): a test asserting no file matches banned patterns beyond a shrinking allowlist.

### 9.3 Kill / Keep / Build inventory (headline)

- **Kill:** `common/Button+Input`, `DataTable`, `QuietTable`, `responsive-rows`, `SectionRail`, `SectionHubPage`, `Drawer` (folds into Sheet), CSS keyframe zoo, film grain on app surfaces, serif in-app, cozy density, 3 of 5 themes (→ Labs, §17 open decision #1).
- **Keep (re-skin):** RailPanel, CommandBar, mobile kit, PageTransition, ErrorBoundary/Skeleton discipline, print stylesheet, `.num`.
- **Build:** SmartTable, StatementTable, FilterBar/BulkBar, SplitView/Inspector, PeriodPicker, Sheet-unified, MoneyInput, DocumentEditor + MatchView scaffolds, notification popover, `/design` catalog, AIExplain.

---

## 10. Dashboard, Forms, Tables & Reports Standards

### 10.1 Dashboard strategy (Today)

Keep the shipped calm order (hero answer → what-needs-you → this-month → collapsed detail) and make it **role-aware**:
- **Owner (default):** exactly what ships today — one answer ("You have ₨ X"), inbox, plain month summary, "More detail" collapsed.
- **Accountant/staff:** work-queue-first — inbox counts (approvals, review queue, exceptions, close tasks) above the money hero; uses `usePermissions` roles, no new backend.
- Baselines on every KPI ("vs last month") — numbers without comparison are decoration.
- Module command centers keep their shape (KPI strip → attention → go-to grid) restyled on Ledger primitives; their stats gain the same baselines.

### 10.2 Forms standard

Single column; `Field` primitive (label-above, help, error slot, `aria-describedby` wired); Zod + react-hook-form everywhere (kill remaining `useState` forms as pages migrate); **MoneyInput** (currency affix, thousands separation while typing, tabular font, no spinners); one filled button per screen; sticky action bar + dirty guard + ⌘Enter on editors; inline validation on blur, submit-blocked summary with focus jump; destructive = typed-confirm Sheet. Multi-step keeps the `trigger()` per-step pattern (BusinessSetup).

### 10.3 Tables standard — `SmartTable` (the workhorse)

- Row 44px (density is fixed); header `label` type; sticky header; column API: `{align, type: text|money|date|status|actions, width}`.
- Money: right-aligned, `money` type token, negative = `money/out` + parentheses option for accountants.
- Sorting, URL-serialized filters (via FilterBar), saved views, column show/hide, CSV/XLSX export hook (existing exportHelpers).
- Selection → BulkBar; hover row-actions (max 2) + overflow menu; full keyboard nav (§7.2).
- **Responsive is built-in, not forked:** `<md` the same column model renders `ListCard` rows (primary/secondary/trailing mapped from column types) with SwipeRow actions — the mobile kit becomes SmartTable's small-screen renderer. The 7 `isMobile` page forks retire (Home keeps its bespoke mobile screen); 90+ pages gain real mobile lists for free.
- Virtualized past 100 rows (`@tanstack/react-virtual`); skeleton rows; EmptyState with one action.
- `StatementTable` variant for reports: 3 indent levels, ledger ruling (single/double rules), inline margin %, bold subtotals — **no zebra, no boxes**.

### 10.4 Reports standard

- **Global PeriodContext** (store + URL param + header control): set once, applies to every statement tab, persists across navigation, shareable URLs. Comparative mode = second period → side-by-side columns + Δ%.
- **Lazy-mount tabs** (fix the 10-way eager mount; keep mount-once-then-preserve per tab).
- Statement hierarchy via StatementTable; **every number drills** — click a P&L line → GL for that account, pre-filtered to the period (route exists; wire params).
- Sticky report toolbar: period · comparative toggle · export · print (print CSS kept) · AI narrative as one collapsible panel (exists — standardize placement).

---

## 11. Search, AI & Discoverability

- ⌘K stays the spine; add **action verbs** to the catalog ("record payment", "reconcile", "close month") so workflows are reachable, not just pages — the catalog + drift-guard infra already supports it.
- **AIExplain**: an ⓘ affordance on hero numbers, KPIs, and statement totals → popover: "How this was calculated" (source figures + period + link to entries). Uses the explainability backend surfaces (Phase 1–6 intelligence cores are live; this is their missing frontend). This is the single most "AI-first, trust-building" visual feature available at low cost.
- Empty states teach: each work view's empty state names its ⌘K phrase and shortcut.
- The `?` shortcut overlay and shortcut hints in tooltips make the keyboard layer discoverable.

---

## 12. Accessibility & Responsiveness

**Target: WCAG 2.2 AA, enforced at the component layer** (a page composed of governed components is compliant by construction):

- Contrast: token-level audit (every ink/surface pair ≥4.5:1; large-text/graphic 3:1); `ink/tertiary` re-tuned on dark.
- Keyboard: full spec per component (Radix supplies overlay/menu/tab semantics); focus-visible ring token; focus trap + return in Sheet; roving tabindex in SmartTable.
- Screen readers: `aria-label` required prop on IconButton (lint-enforced); table `scope`/caption in SmartTable; `role=status` on toasts; `aria-live=polite` on async counts; chart data-table alternatives.
- Status = icon + text + color, never color alone (StatusChip enforces).
- Motion: `useReducedMotion` fallbacks in the motion module (guard exists globally, becomes per-component).
- Touch: 44px targets (tap-target utility exists), safe-areas (exist), 24px minimum spacing per WCAG 2.2.
- Responsiveness: 4 breakpoints (375/768/1024/1440) verified per wave; SmartTable card-collapse (§10.3) is the systemic answer; `MobilePage`/`Sheet` continue as the small-screen scaffold; no horizontal page scroll ever (wide content scrolls inside its container).
- RTL: logical properties (`ps-/pe-`) in all new components so Urdu RTL works by construction.

**Performance budget (enforced in CI later):** initial JS <250kB gz (manualChunks exist — keep); LCP <2.5s on Today; remove z-60 grain + reduce backdrop-blur surfaces (paint cost); virtualize ledgers; lazy-mount report tabs; `content-visibility:auto` on long dashboards; fonts subset + `font-display:swap`; three.js/ogl stay landing-only chunks.

---

## 13. Future Scalability (design now, ship later)

- **Multi-organization:** switcher slot in shell (§6); all Query keys already tenant-scoped by token — UI swap = cache reset + refetch. Data-model work is a separate backend spec.
- **AI surfaces:** Intelligence pages (phases 1–6 cores) get their frontends as Work-View + Inspector instances — no new patterns needed; AIExplain (§11) is the wedge. Autonomy Command Center already matches the Inbox pattern.
- **Module marketplace-readiness:** module enablement exists; nav/config-driven IA means a future module = config entry + pages built from the five surfaces.
- **White-label/theming:** because components reference only semantic tokens, a future customer theme = one value file — the *reason* to kill palette-name classes now.
- **i18n:** extraction happens per migration wave (the copy passes through components anyway); Urdu completes module-by-module.
- **Design-token export:** tokens live as CSS vars + a JS mirror (`tokens.js`) so charts/canvas/emails can consume them; a future Figma sync reads the same file.

---

## 14. What is explicitly kept from today (so this isn't read as a teardown)

The IA and nav model; ⌘K command bar (all 4 phases); the token *engine*; TanStack/Zustand/Axios data layer; route table + redirects; print stylesheet; `.num`; plain-language copy voice; smart/simple transaction entry UX; the mobile kit components; PageTransition; per-page error boundaries; the calm dashboard order; Atelier's warm-black + champagne identity (as the seed of Ledger Dark); Daybreak (as the seed of Ledger Light); the landing page (untouched by this spec, remains the expressive brand exterior).

---

## 15. Success Criteria

1. **One language:** any two screens side-by-side read as the same product; `/design` catalog shows 100% of shipped components in both modes.
2. **Zero legacy vocabulary:** lint reports 0 arbitrary font sizes (baseline: 976 occurrences), 0 palette-name color classes (baseline: 646), 0 raw `<table>` outside `design-system/data` (baseline: 37 files) — enforced, not aspirational.
3. **One of each:** 1 Button, 1 Input, 1 table system, 1 modal/sheet system, 1 motion engine in the tree; the kill-list files deleted.
4. **Workflows finish in place:** record payment / approve / remind / match without leaving the list (≤1 click each from the row); reconciliation session fully keyboard-drivable.
5. **Reports:** period survives tab switches and lives in the URL; every statement number drills to GL; only the visible tab fetches on entry.
6. **Mobile:** every Work-View page renders as cards at 375px with no horizontal scroll — without a hand-built fork.
7. **A11y/perf:** AA contrast across both modes; keyboard path through shell + one full workflow; initial bundle <250kB gz; Today LCP <2.5s.
8. **Governed forever:** the ESLint ratchet + drift-guard tests are in CI, so entropy cannot regrow — the property that distinguishes this program from the two prior unfinished migrations.

---

## 16. Implementation Roadmap (phased, shippable, each with a deletion gate)

> Sizes: S ≈ days, M ≈ 1wk, L ≈ 2wk+. Order rationale: **governance before pixels** (or the third migration dies like the first two), **workhorse before workflows** (every workflow surface stands on SmartTable), **chrome after primitives** (shell v2 uses them), **sweeps last** (cheap once the system exists).

| # | Phase | Ships | Gate (must delete/enforce) | Size |
|---|---|---|---|---|
| 0 | **Foundations & governance** | tokens v2 (semantic vocabulary over `--c-*`), Ledger Dark/Light value sets, motion module, ESLint rules (warn), `/design` catalog shell, drift-guard test, dead-code purge | delete `SectionRail`, `SectionHubPage`, nav legacy aliases; grain off app surfaces; density toggle retired | M |
| 1 | **Primitives** | Button/IconButton/Field/Input/MoneyInput/Select/Badge/StatusChip/Tooltip/Money/Delta/Card/Sheet/Menu/Tabs/Section/PageHeader/EmptyState/Skeleton/Toast (Radix-backed where adopted) | delete `common/Button`, `common/Input`, `Drawer`; migrate auth + settings pages (the simplest wave) as proof | L |
| 2 | **SmartTable + FilterBar + BulkBar + SplitView/Inspector** | the workhorse with responsive card-collapse, virtualization, saved views | convert 5 anchor lists (Transactions, Invoices, Bills, Customers, Receivables); delete `QuietTable`; shrink `DataTable` allowlist | L |
| 3 | **App Shell v2** | header rebuild (breadcrumbs-deep-only, notification popover, + New, org-switcher slot), rail/panel re-skin, keyboard map + `?` overlay, mobile menu regenerated from nav.config | delete `MobileMenuSheet` duplication; shortcut hints live | M |
| 4 | **Reports v2** | PeriodContext (store+URL+header), lazy-mount tabs, StatementTable with ledger ruling, drill-through to GL, comparative columns | delete per-tab date pickers; eager mount removed | L |
| 5 | **Work-View wave 2** | remaining lists (Vendors, Payables, POs, GRNs, Approvals, Review/Exception queues, Assets, Inventory, Employees…) onto SmartTable; inline actions (record payment, remind, approve) via Inspector | delete `DataTable`, `responsive-rows`; lint rules → error for migrated dirs; retire list-page `isMobile` forks | L |
| 6 | **Document Editor v2** | one scaffold → Invoice, Bill, PO editors; TransactionFormModal decomposed (Simple front kept) | the three bespoke editors reduced to compositions; modal <600 lines | L |
| 7 | **Today + command centers v2** | role-aware Home, KPI baselines, module centers on Ledger primitives, AIExplain on hero numbers | CSS keyframe zoo deleted (motion module covers all) | M |
| 8 | **Match View** | reconciliation + AI review + exceptions on the two-pane keyboard surface | bespoke reconciliation layouts retired | M |
| 9 | **Close Cockpit** | Accounting → Close checklist + lock-period flow (existing APIs) | — (new surface) | M |
| 10 | **Hardening sweep** | i18n extraction completion (+Urdu per module), a11y certification pass, perf budget in CI, theme Labs-gating per open decision #1, visual QA at 4 breakpoints × 2 modes | lint ratchet → error globally; success criteria §15 measured | M |

**Dependencies:** 0→1→2 strictly ordered; 3–4 parallelizable after 1; 5 after 2; 6–9 after their surface dependencies; 10 last. **Every phase leaves production shippable** — waves migrate whole modules so no user journey crosses a style boundary mid-flow (the current pile-up's core failure).

---

## 17. Open decisions for the user (defaults chosen so work can start)

1. **Theme sprawl → 2 first-class modes.** *Recommended & assumed:* Ledger Dark + Ledger Light ship; Eclipse/Terminal/Maison move behind a "Labs" Appearance flag (kept for demo value, excluded from QA guarantees). Alternative: keep all 5 first-class — accepts the 10-matrix QA cost and weakens "one language" permanently.
2. **Density toggle retired** (calm becomes the only density). Alternative: keep cozy — doubles visual QA again.
3. **Radix primitives adopted** for overlay/menu/form semantics (~40kB, a11y by construction). Alternative: zero new deps, hand-rolled ARIA (adds ~2 phases of effort and ongoing risk).
4. **Serif leaves the app shell** (stays on landing). Alternative: keep Maison/Atelier serif in-app — conflicts with figure-first typography.

---

*Next step after user review: invoke `superpowers:writing-plans` to turn Phase 0 (+1) into an executable TDD implementation plan.*
