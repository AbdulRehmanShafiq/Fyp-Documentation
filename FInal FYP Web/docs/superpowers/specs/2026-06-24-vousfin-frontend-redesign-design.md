# VousFin Frontend Redesign — Design Spec

- **Date:** 2026-06-24
- **Status:** Approved direction (grouping + nav model locked); ready for implementation planning
- **Author:** Design audit (Principal Product Designer / FinTech UX / IA / Design Systems)
- **Scope:** `vousfin-frontend-main/` — React 19 + Vite SPA. Frontend-only, except module enablement (Phase 2) and role-gated nav, which may need a small additive backend config field (handled within that phase; see §13).

---

## 1. Goal & Guiding Principle

Transform VousFin into **"the accountant's operating system"**: simple enough for a non-accountant business owner to run their books, complete enough that a professional accountant can do all their work without feeling the tool is less capable than QuickBooks/Xero/NetSuite.

**North-star (one paragraph):** A 64px always-visible module rail + a contextual panel that turns each module into its own live command center; an information architecture of six always-on modules (Home, Sales, Purchases, Banking, Accounting, Reports) plus three enableable ones (Payroll, Planning, Tax & Compliance) and Settings — every existing page given a clear home and a dual plain/accounting label; a dashboard that leads with one hero cash metric and a needs-you inbox; reports with real statement hierarchy under a single global period; inline actions wherever data lives; one canonical set of primitives and semantic tokens; atmosphere kept for showpiece screens and stripped from data-dense ones; two shipping themes; and a roadmap to a business switcher and Cmd-K. **No rewrite** — every change is an incremental, backward-compatible layer over the existing CSS-variable engine and route table.

**Hard constraints:**
- Backward-compatible: existing routes keep working (redirects where paths move).
- Incremental: each phase is shippable on its own; production never breaks between phases.
- Reuse the existing CSS-variable theme engine and `nav.config` as the single source of truth.
- Plain language is primary in user-facing copy (per project copy rules); accounting terms are secondary/contextual.

---

## 2. Decisions Locked (from brainstorming)

| Decision | Choice |
|---|---|
| Primary users | Both — owner-simple AND accountant-complete (dual-label IA) |
| Module grouping | **6 always-on + 3 enableable + Settings** (see §4) |
| Module enablement | Yes — businesses turn off modules they don't use; nav + routes respect it; role-gated via `usePermissions` |
| Navigation model | **Hybrid Rail + Contextual Panel** (64px rail always visible + 216px module panel) |
| Sidebar width | ~280px total (64 rail + 216 panel); panel collapsible to rail-only |
| Command palette (Cmd-K) | Deferred to roadmap (post-MVP), but nav designed to accept it |
| Themes | Ship 2 (Atelier dark default, Daybreak light); others behind a "Labs" flag |
| Fonts | IBM Plex Sans (UI) + Spline Sans Mono / IBM Plex Mono (numbers) |

---

## 3. Audit Summary (why we're doing this)

Findings were produced via an initial audit + three iterative critique loops (re-audit, attack-the-redesign, elite-panel review) grounded in competitor research (Xero, QuickBooks, Zoho Books, Ramp/Mercury/Brex).

### Critical issues
1. **2-click navigation tax** — rail icon → hub page → module on every workflow.
2. **9 flat top-level sections** — exceeds 7±2 comprehension limit.
3. **"Money In/Money Out" labels** — not the accountant's vocabulary; needs dual-label.
4. **Bank Reconciliation buried** under "Autopilot" — competitors elevate banking.
5. **Three different money formatters** (`formatters.formatCurrency`, `Dashboard.fmtAmt`, `SectionHubPage.compactMoney`) — a trust bug.
6. **A second full nav system is dead code** (`Sidebar.jsx` consumes `NAV_SECTIONS` but `DashboardLayout` renders `SectionRail`; `MobileMenuSheet` is a third surface).
7. **No global search; dead notification bell** (`Header.jsx` bell has no handler).
8. **Theme-palette names baked into components** (`text-cyan`, `text-gold`, `text-amber`, `text-emerald-3`) — breaks theming/semantics.
9. **No standard PageHeader; reinvented empty/loading/error states.**
10. **No global report period context** — switching statements loses the date range.

### Secondary
- Duplicate `Button`/`Input`/`Export` components (`ui/*` vs `common/*` vs `reports/*`).
- Duplicate approval-count polling (rail + sidebar).
- Transaction-type logic duplicated across Dashboard and TransactionsList.
- Arbitrary px font sizes (`text-[12px]`/`[12.5px]`/`[13px]`/`[15px]`).
- No `prefers-reduced-motion` guard on aurora/grain/animations; no print stylesheet.
- Atmosphere effects (grain/aurora) compete with data on dense report/table screens.
- No multi-business switcher (blocks accountant-with-clients at scale).
- Mobile is second-class (only Home + Reports as direct destinations).

### What to preserve (already excellent)
CSS-variable token engine · `.num` mono numbers · `transition-premium` timing · `premium-card` · film grain + aurora (on showpiece screens) · raised mobile ⊕ Create · section accent colors as identity · ErrorBoundary + Suspense lazy-loading · TanStack Query 5-min staleTime.

---

## 4. New Information Architecture

**Naming principle (dual-label):** top-level uses a word both audiences know; each module's command-center subtitle restates it in plain language; accounting terms live on sub-items and tooltips.

### Always-on modules (6)

```
HOME            "Your business at a glance"
  Dashboard · Command Center inbox (folded into Home)

SALES            "Money coming in"            [AR]
  Customers · Invoices · Receivables · AR Aging

PURCHASES        "Money going out"            [AP + Procurement]
  Vendors · Bills · Payables · Purchase Orders · Goods Receipts · AP Workflow

BANKING          "Cash, bank feeds & matching"
  Bank Reconciliation · AI Review Queue · Reconciliation Exceptions
  · Transactions (cash/bank) · Recurring

ACCOUNTING       "The books"                  [General Ledger]
  Chart of Accounts · Journal Entries · Approvals · Fixed Assets
  · Inventory · Fiscal Years · Activity / Audit Trail · Internal Audit

REPORTS          "Statements & filings"
  Financial Statements (P&L · Balance Sheet · Cash Flow · Trial Balance
  · General Ledger · Equity · Comparative · Aging) · Report Builder · Tax Reports
```

### Enableable modules (3)

```
PAYROLL          "Pay your team"
  Employees · Run Payroll · Payslips

PLANNING         "Look ahead & dig in"        [Management accounting / FP&A]
  Forecast · Scenarios · 13-Week Cash · Budgets · Budget vs Actual
  · Job Costing · Profitability · Break-even · Benchmarking · Anomalies · AI Assistant

TAX & COMPLIANCE "Stay compliant"
  Tax Autopilot · Compliance Calendar · Leases & Impairment · AML Screening
```

### Pinned

```
SETTINGS         "Configure VousFin"
  Business · Team · Roles & Duties (SoD) · Security · Tax Engine
  · Exchange Rates · Cost Centres · Appearance
```

### Complete page → module mapping (every existing route assigned a home)

| Existing route | New module | Notes |
|---|---|---|
| `/dashboard` | Home | + Command Center inbox folded in |
| `/command-center` | Home | becomes the Home "needs you" inbox |
| `/customers`, `/customers/:id` | Sales | |
| `/sales/invoices*` | Sales | |
| `/sales/receivables` | Sales | |
| (AR aging view) | Sales | sourced from existing aging report |
| `/vendors`, `/vendors/:id`, `/vendors/:id/portal` | Purchases | |
| `/purchases/bills*` | Purchases | |
| `/purchases/payables` | Purchases | |
| `/procurement/purchase-orders*` | Purchases | |
| `/procurement/goods-receipts` | Purchases | |
| `/purchases/ap-workflow`, `/purchases/procurement-dashboard` | Purchases | |
| `/reconciliation/bank` | Banking | promoted out of Autopilot |
| `/ai/review-queue` | Banking | bank-matching task |
| `/reconciliation/exceptions` | Banking | |
| `/transactions`, `/transactions/templates` | Banking + Accounting | cash/bank view in Banking; full ledger/journal in Accounting (same data, two lenses) |
| `/accounts` | Accounting | Chart of Accounts |
| `/approvals` | Accounting | also surfaced as cross-cutting Home inbox queue |
| `/assets` | Accounting | Fixed Assets |
| `/inventory` | Accounting | |
| `/accounting/fiscal-years` | Accounting | |
| `/activity` | Accounting | Audit Trail |
| `/audit/internal` | Accounting | Internal Audit |
| `/financial-reports/*`, `/financial-reports/builder` | Reports | |
| (tax report tab) | Reports | + cross-linked from Tax & Compliance |
| `/payroll/*` | Payroll (enableable) | |
| `/ai-analyst/forecast`, `/ai-analyst/scenarios`, `/ai-analyst/anomalies` | Planning (enableable) | |
| `/cash/thirteen-week` | Planning | |
| `/budgets/editor`, `/budgets/variance` | Planning | |
| `/cost/jobs`, `/cost/profitability`, `/cost/break-even` | Planning | |
| `/analysis/benchmarking` | Planning | |
| `/ai/assistant` | Planning | + ambient launcher |
| `/tax` (Tax Autopilot) | Tax & Compliance (enableable) | |
| `/compliance/calendar`, `/compliance/leases`, `/compliance/aml` | Tax & Compliance | |
| `/settings/*`, `/business/settings` | Settings | consolidate URL namespaces over time |

**Result:** a simple business sees ~6–7 modules; a full ERP user enables all and sees ~9 + Settings. Most users land within the 7±2 comprehension target.

---

## 5. Navigation Architecture — Hybrid Rail + Contextual Panel

```
┌────┬───────────────────────┬────────────────────────────┐
│ 64 │  Contextual Panel      │   Content / Command Center │
│ px │  (active module's      │                            │
│rail│   sub-items, 216px)    │                            │
│ ▦  │  ← SALES               │   [module command center]  │
│ ◐  │   Customers            │                            │
│ ◑  │   Invoices             │                            │
│ ◒  │   Receivables          │                            │
│ ◓  │   AR Aging             │                            │
│ ⋯  │                        │                            │
│ ⚙  │                        │                            │
└────┴───────────────────────┴────────────────────────────┘
```

- **64px icon rail** — every top-level module, always visible, **1 click to anywhere** (kills the 2-click tax and preserves cross-module speed for month-end work). Active module glows in its section accent (existing pattern).
- **216px contextual panel** — sub-items of the active module; header shows `← Module Name`; top item is the module's command center. Sub-items grouped with light dividers (Customers / Invoices / Receivables).
- **Collapsible** — panel collapses to rail-only for dense report work; preference persisted per user.
- **Header (per page)** — breadcrumb trail (`Banking › Bank Reconciliation`) + **global search** + **notifications panel** + profile menu (+ business switcher on roadmap).
- **Mobile** — bottom bar: Home · current-module · ⊕ context-create · AI · Menu; Menu opens a full-screen module sheet; module command centers are first-class on mobile.
- **Single source of truth** — extend `nav.config.js`; **delete** `Sidebar.jsx` and retire `MobileMenuSheet` in favor of one mobile sheet driven by the same config.

**Motion:** one signature transition — rail→panel shared-axis slide, 220–260ms `cubic-bezier(0.32,0.72,0,1)`, staggered sub-item fade (~30ms). Everything else stays calm. Respect `prefers-reduced-motion`.

---

## 6. Module Command Centers

Landing on a module shows its dashboard (the "dashboard of that module" requested by the user):

```
[Icon] MODULE NAME                         [context New ▾] [•••]
plain-language subtitle
────────────────────────────────────────────────────────────
KPI strip (3–4 numbers WITH comparison baselines)
────────────────────────────────────────────────────────────
NEEDS ATTENTION (module-scoped)   │   RECENT ACTIVITY
• item + inline actions           │   compact rows
────────────────────────────────────────────────────────────
GO TO: [sub-module] [sub-module] [sub-module]   (replaces hub cards)
```

| Module | KPIs | Quick actions |
|---|---|---|
| Sales | Revenue (mo), AR outstanding, Overdue count, Avg invoice | New Invoice, Record Payment, Send Reminder |
| Purchases | Expenses (mo), AP outstanding, Bills overdue, Next due | New Bill, Pay Vendor, New PO |
| Banking | Unreconciled count, AI queue, Unmatched items, Last sync | Reconcile, Review Queue, Import |
| Accounting | Pending approvals, Journal entries (wk), Period status | New Journal, Approve, Close Period (roadmap) |
| Reports | Net income, Revenue vs budget %, Cash, Margin | Open P&L, Export, Build Report |
| Planning | Runway, Forecast vs actual, Budget variance, Burn | Run Forecast, Edit Budget, Ask AI |
| Tax & Compliance | Tax position, Next deadline, Open obligations | View Tax, Calendar, Screen |

---

## 7. Dashboard Strategy (Home)

Inverted pyramid — most critical first:

1. Greeting + **context-aware quick actions**.
2. **Hero cash metric** (one number that answers "am I OK?").
3. **Needs-Attention inbox** (Command Center folded in; cross-cutting approvals; overdue AR; bills due; unmatched bank items) with **inline actions**.
4. Supporting KPIs **with comparison baselines** (vs last month / vs budget).
5. **One** interpreted chart (with an AI one-line read: "Revenue +8% vs last month").
6. AI outlook — a single narrative line, not a large widget.
7. Recent activity (compact).
8. **First-run setup checklist** for new owners (Add customer → Send invoice → Connect bank → …).

Atmosphere (grain/aurora) stays on Home; it is **stripped on data-dense pages** (reports, tables, editors).

---

## 8. Reports Strategy

- **Global period context** — one date/fiscal-period selector applies across all statement tabs (set once, persists across P&L → Balance Sheet → …).
- **Statement visual hierarchy** — Revenue / Gross Profit / Net Income visually larger; subtotals bold; detail regular; inline margin % (48%, 26%).
- Sticky report toolbar (period + export + share-URL with period as query params).
- AI narrative becomes a collapsible bottom panel, not repeated under each table.
- Print stylesheet for clean PDF/print output.

---

## 9. Design System Direction

### 9.1 Consolidate primitives (one canonical each)
- `Button` → keep `ui/Button.jsx`; delete `common/Button.jsx`; migrate imports.
- `Input` → keep `ui/Input.jsx`; delete `common/Input.jsx`; migrate imports.
- Export → merge `reports/ExportButtons.jsx` into `ui/ExportButton.jsx`.
- New shared primitives: `PageHeader`, `EmptyState`, `ErrorState`, `LoadingState`, `Money`.

### 9.2 Token layers (components reference roles, never palette names)
```css
/* Semantic status — decoupled from section accents */
--c-status-success: var(--c-positive);
--c-status-danger:  255 72 72;            /* errors / overdue only */
--c-status-warning: var(--c-highlight);   /* pending / attention */
--c-status-info:    var(--c-accent);      /* neutral info */

/* Type scale — no arbitrary px in components */
--text-label: 11px; --text-xs: 12px; --text-sm: 13px; --text-base: 14px;
--text-md: 15px; --text-lg: 17px; --text-xl: 20px; --text-2xl: 24px; --text-display: 32px;
```
- Replace `text-cyan`/`text-gold`/`text-amber`/`text-emerald-3` usages with status/role tokens.
- Section accents (`--sec-*`) remain **identity only**, never status.

### 9.3 Single money formatter
- One `formatCurrency` + `Money` component, business-currency aware (no hardcoded `PKR`/`Rs`), used everywhere. Delete `Dashboard.fmtAmt` and `SectionHubPage.compactMoney`; add a `compact` option to the shared formatter.

### 9.4 Other system fixes
- Centralize transaction-type classification (one module, imported by all views).
- One shared approvals poller (single query key).
- `prefers-reduced-motion` guards on aurora/grain/animations.
- Print stylesheet.
- Themes: ship Atelier (dark) + Daybreak (light); gate Eclipse/Terminal/Maison behind a Labs flag.

---

## 10. Accessibility

- `aria-label` on all icon-only controls (rail items, bell, profile, row actions).
- Breadcrumb navigation rendered (use existing `Breadcrumbs.jsx`).
- Status never color-only — pair icon + color.
- `scope` on report table headers; associate labels with inputs.
- Focus management for rail/panel transitions and modals; visible focus rings (already present via `focus-visible` ring).
- Honor `prefers-reduced-motion`.

---

## 11. Components & Files Affected (non-exhaustive)

- **Nav:** `components/layout/nav.config.js` (extend: modules, enablement, roles), new `RailPanel` component set, `DashboardLayout.jsx`; **delete** `Sidebar.jsx`; consolidate `MobileNav.jsx` + `MobileMenuSheet.jsx`.
- **Header:** `components/layout/Header.jsx` (breadcrumb + search + notifications + profile menu).
- **Primitives:** `components/ui/*` (Button/Input/Select/PageHeader/EmptyState/ErrorState/LoadingState/Money); remove `components/common/Button.jsx`, `components/common/Input.jsx`.
- **Hubs → Command Centers:** `pages/hub/SectionHubPage.jsx` evolves into per-module command centers.
- **Dashboard:** `pages/dashboard/Dashboard.jsx` (inversion, hero metric, inbox, baselines).
- **Reports:** `pages/reports/FinancialReportsPage.jsx` + statement pages (global period, hierarchy, sticky toolbar, print).
- **Tokens:** `src/index.css`, `src/theme/themes.js` (status tokens, type scale, theme gating).
- **Utils:** `utils/formatters.js` (single money formatter), new `utils/transactionTypes.js`.

---

## 12. Implementation Roadmap (phased, shippable, backward-compatible)

| Phase | Name | Ships | Risk |
|---|---|---|---|
| 1 | **Nav Foundation** | Hybrid rail+panel; one nav source; delete dead `Sidebar.jsx`; breadcrumb header; route redirects | Med |
| 2 | **IA Reorg + Enablement** | 6+3 module grouping & names; module enablement; role-gated nav; page→module remap | Med |
| 3 | **Module Command Centers** | Per-module dashboards (replace hub pages) | Large |
| 4 | **Design System Cleanup** | Consolidate primitives; status + type tokens; **single money formatter**; centralize tx-type logic; one approvals poller | Med |
| 5 | **Dashboard Redesign** | Hero metric + needs-attention inbox; KPI baselines; AI narrative; first-run checklist | Med |
| 6 | **Reports Redesign** | Global period; statement hierarchy; sticky toolbar; share-URL; print | Med |
| 7 | **Workflow Inline Actions** | Record Payment / Pay Now / Reconcile inline; context-aware New; save-and-add-another | Large |
| 8 | **Mobile Redesign** | Module command centers on mobile; single mobile sheet; deeper direct destinations | Med |
| 9 | **Accessibility + Polish** | aria/labels/scope; reduced-motion; scoped atmosphere; signature motion; 2-theme ship | Med |
| R | **Roadmap (post-MVP)** | Business switcher; Cmd-K palette; month-end close; saved views; bulk actions; realtime notifications; onboarding tour; density toggle | — |

**MVP of the redesign = Phases 1–3** (the "accountant's OS" transformation). Phase 1 alone removes the 2-click tax.

---

## 13. Out of Scope (this spec)
- Backend/API changes (module enablement and roles use existing config/permissions where possible; any new persistence is a small additive change handled in its phase).
- Multi-tenant data model for true multi-company (switcher is UI-roadmap; data model is a separate spec).
- Command palette implementation (roadmap).

---

## 14. Success Criteria
- Any module reachable in **1 click** from anywhere (desktop).
- Default business sees **≤7** top-level modules; all numbers formatted **identically** app-wide.
- **One** nav system, **one** Button/Input, **one** money formatter in the codebase.
- Dashboard answers "am I OK?" in **<2 seconds** (hero metric + inbox above the fold).
- Reports keep the chosen **period across all statements**; totals visually dominant.
- Owner can operate without accounting knowledge; accountant finds every pro feature with parity to QuickBooks/Xero.
