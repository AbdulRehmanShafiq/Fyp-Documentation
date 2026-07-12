# Very-Easy VousFin — First Pass: The Daily Core Loop

**Date:** 2026-07-12
**Status:** Approved (design walkthrough, user delegated execution)
**Repo:** `vousfin-frontend-main` (frontend-only; no backend/API change)

## Goal

Make the screens a non-accountant owner touches every day feel **very easy**: calm minimal default, plain-English wording, one obvious action. This first slice — the **daily core loop** — becomes the template for the same three moves (calm default · one tap · plain words) applied module-by-module later.

## Approach (locked with user)

- **First slice:** the daily core loop — Dashboard + recording money + seeing where you stand.
- **Simple vs power:** simplify the default and tuck details away. One clean experience for everyone; power is a click deeper, never removed. No mode switch.

## Non-goals

- No changes to other modules' pages in this pass (Sales/Purchases/Banking/etc. internals).
- No backend/API/accounting changes. Numbers and behaviour are unchanged — only layout, grouping, and wording change.
- No removal of any existing widget — everything stays reachable (collapsed here, and still in its own module).

## Design

### 1. Calm dashboard (`src/pages/dashboard/Dashboard.jsx`)

Reorder so the "do now / am I OK" essentials are above the fold and the "look later" analytics collapse into one section.

**Above the fold (always visible), in order:**
1. Greeting header (unchanged).
2. **Cash on hand** hero (`CashHero`, unchanged).
3. **Quick actions** — plain relabels (see §3): `Record something` · `Send an invoice` · `See who owes me` · `See what I owe`.
4. **What needs you** — the `CommandCenterWidget` preview (already built) stays; the standalone `NeedsAttentionFeed` section is folded in under the same "What needs you" heading directly beneath it (two cards under one heading, not two separate sections).
5. **This month** — a new compact `MoneyInOutCard`: money coming in, money going out, and what's left, in plain words, from existing `kpis.revenue` / `kpis.expenses` / `kpis.netProfit`. Links to Reports for detail.

**Collapsed by default (one "More detail" section):**
- A single collapsible `Section` titled **"More detail"** (`defaultOpen={false}`) wrapping, in order: KPI strip (`SmartKPIStrip`), "How your business is doing" (`TaxPositionWidget` + `BusinessHealthWidget` + `BusinessOutlookWidget`), the analytics charts (`RevenueExpensesChart` + `CashFlowTrendChart`), and forecasting (`FinancialSnapshot` + `ForecastWidget`).
- **Recent activity** stays visible below (it's plain and useful), unchanged.

`ModuleShortcuts` ("Jump back in") stays where it is — it's already minimal and learned per user.

The existing `Section` component already supports `collapsible` + `defaultOpen` and animates — reuse it, no new collapse mechanics.

### 2. Recording money — one tap, plain

The transaction modal already defaults to Simple mode (six plain chips, `localStorage['vf-entry-mode']='simple'`). This pass only:
- Confirms the dashboard's `Record something` opens the modal in Simple mode (it uses the shared `openTxModal`; Simple is already the default — verify, no code change expected).
- No structural change to the modal.

### 3. Plain words on the daily-loop surfaces

Update **only** the copy on the dashboard + the two "position" cards. Owner language is the visible text; the accounting term may appear as a small secondary hint where it already does.

| Current | Plain (visible) |
|---|---|
| Quick action "Record Transaction" | **Record something** |
| Quick action "New Invoice" | **Send an invoice** |
| Quick action "Chase Payment" | **See who owes me** |
| Quick action "Pay a Bill" | **See what I owe** |
| Section "Key Metrics" | **Your numbers** |
| Section "Business Intelligence" | folded into **More detail** |
| Section "Business Analytics" | **Charts** (inside More detail) |
| Section "Forecasting & Cash Position" | **What's coming** (inside More detail) |
| Section "Needs your attention" | **What needs you** |
| `FinancialSnapshot` "Accounts Receivable" | **Money owed to you** (keep "Accounts Receivable" as the small caps sub-label already present) |
| `FinancialSnapshot` "Accounts Payable" | **Money you owe** (keep sub-label) |

Wording changes go through the i18n keys in `src/i18n/locales/en.json` (and mirror the new keys in `ur.json` with the English value as placeholder so nothing renders blank) — matching the existing `t('dashboard.*')` pattern. New user-facing strings that aren't yet keyed may be added as literals consistent with surrounding code, but reuse existing `dashboard.*` keys where they exist (recordTransaction, newInvoice, chasePayment, payBill, keyMetrics, businessAnalytics, forecastingCash, recentActivity, needsAttention).

## Components

- **New:** `src/components/dashboard/MoneyInOutCard.jsx` — pure presentational; props `{ income, expenses, net, currency, loading }` (Dashboard passes `kpis.revenue`, `kpis.expenses`, `kpis.netProfit`); three plain rows + "what's left" emphasis; link to `/financial-reports/income-statement`. Uses `formatCompactCurrency`.
- **Modified:** `Dashboard.jsx` — reorder sections, wrap analytics block in one collapsed `Section`, merge needs-attention under "What needs you", swap in plain labels, render `MoneyInOutCard`.
- **Modified:** `en.json` / `ur.json` — plain-word values for the affected `dashboard.*` keys + any new keys.

## Testing

- **Unit (Vitest):** `MoneyInOutCard.test.jsx` — renders income/expenses/net, formats currency, shows a "loading" skeleton when `loading`, and computes "what's left" = income − expenses when `net` absent. (Pure component, deterministic.)
- **Existing suites** must stay green (89 tests): dashboard has no test today, so the risk is the catalog-manifest drift guard (nav untouched here → unaffected) and the smoke test.
- **Build** must pass (`npm run build`).
- **Live verify** in the preview: dashboard renders calm (essentials up top, "More detail" collapsed), `Record something` opens Simple mode, no console errors, and the collapse expands/restores every widget unchanged.

## Rollout / template

Once approved live, the same three moves become the repeatable pattern for the next passes (one module at a time): calm default (essentials up, rest collapsed/relocated) · one obvious action · plain words with the accounting term as a quiet secondary.
