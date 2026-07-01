# 09 — Reporting Engine

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Every report: purpose, source, filters, math, validation, performance |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> Reports are **derived**, never stored. Every figure traces to journal records. If a report disagrees with the ledger, the report is wrong — fix the report, never patch the number.

---

## 1. Purpose & scope

Specify each report's data source, filters, calculation, validation, and performance characteristics. Endpoints live under `routes/v1/report.routes.js` (`/api/v1/reports/*`) plus AR/AP (`arApReport.routes`), CFO (`cfoReport.routes`), tax (`tax.routes`), 13-week cash flow, and benchmarking routes. Services: `report.service`, `reportBuilder.service`, `arApReporting.service`, `cfoReport.service`, `narrative.service`, `taxReport.service`.

## 2. Universal principles

1. **Derived from `JournalEntry.journalLines[]`** via `transaction.repository.EFFECTIVE_LINES_STAGE` (uses `journalLines`, else synthesizes the pair) — so reports natively handle compound entries.
2. **Status filter.** Reports include balance-affecting statuses (posted, partially_settled, settled, reversed) and exclude archived unless explicitly requested.
3. **Tenant-scoped + period-filtered.** Every query filters `businessId` and a date range.
4. **Cached.** Hot reports use `reportCache` (30s–5min TTL, invalidated on every write) — Doc 11.
5. **Reproducible.** Same inputs + same ledger → same output; historical FX/rates immutable.
6. **Reconciled.** Each report ties back to the ledger (Validation Engine VE-8…VE-12).

## 3. Report catalog

### 3.1 Trial Balance — `GET /reports/trial-balance`
- **Purpose.** List every account's debit/credit balance; prove Σdebits = Σcredits.
- **Source.** Per-account debit/credit totals from journal lines.
- **Filters.** `asOf` date, include-zero flag.
- **Calc.** For each account, net by `normalBalance`; total both columns.
- **Validation.** Columns must be equal (VE-1). Ties to `computeDrift.balanced`.

### 3.2 General Ledger — `GET /reports/general-ledger`
- **Purpose.** Chronological line detail per account with running balance.
- **Source.** Journal lines for the account in range, ordered by date.
- **Filters.** `accountId`, date range, pagination.
- **Calc.** Opening balance + cumulative debit/credit → running balance.
- **Validation.** Closing running balance == account balance for the range.

### 3.3 Income Statement (P&L) — `GET /reports/income-statement` (aliases `/profit-loss`, `/profit-and-loss`)
- **Purpose.** Revenue − COGS − expenses = net income for a period.
- **Source.** Revenue (4xxx), Direct cost (5xxx), Expenses (6xxx) journal lines.
- **Filters.** Period, cost-centre, comparative period.
- **Calc.** Gross profit = Revenue − COGS; Net income = Gross profit − Operating expenses (± other income/expense, FX, tax).
- **Validation.** Net income flows to Current Year Earnings / Retained Earnings (VE-9).

### 3.4 Balance Sheet — `GET /reports/balance-sheet`
- **Purpose.** Financial position: Assets = Liabilities + Equity.
- **Source.** Asset/Liability/Equity account balances as-of date; current-year earnings from P&L.
- **Validation.** Must balance (VE-8); contra accounts (1250, 1267) net correctly.

### 3.5 Cash Flow — `GET /reports/cash-flow`
- **Purpose.** Operating/Investing/Financing cash movements.
- **Source.** Cash/bank account (10xx) movements classified by `transactionCategory` / counter-account.
- **Validation.** Net change == closing − opening cash (VE-10).

### 3.6 Aging (AR/AP) — `GET /reports/aging`, `arApReport` routes
- **Purpose.** Outstanding receivables/payables bucketed (current, 30/60/90/90+).
- **Source.** Open invoices/bills with `remainingBalance` and `dueDate`.
- **Validation.** Σ buckets == total outstanding == control-account balance (VE-11).

### 3.7 Tax Summary — `GET /reports/tax-summary`, tax routes
- **Purpose.** Output tax, input tax, net payable per period/type.
- **Source.** `taxAmount`/`taxType` on entries; tax-position snapshots.
- **Validation.** Net payable ties to tax-payable GL balances (VE-12).

### 3.8 Statements of Equity & Liabilities — `/reports/equity`, `/reports/liabilities`
- Equity roll-forward (opening + contributions − drawings + net income) and liability composition.

### 3.9 Comparatives & KPIs — `/reports/comparative/income`, `/comparative/balance`, `/reports/kpi`
- Period-over-period deltas; ratio KPIs (margins, liquidity, turnover). Benchmarking via `benchmarking.service` (sector radar).

### 3.10 Customer / Vendor Statements
- `customerStatement.service` / vendor equivalents: per-party ledger of invoices, credits, payments, running balance.

### 3.11 Notes & Narrative — `/reports/notes/revenue`, `/reports/narrative`
- Financial-statement notes; `narrative.service` generates plain-language commentary (AI-assisted, grounded in the figures).

### 3.12 Inventory reports
- Valuation (Σ qty×cost, ties to GL 1150), aging, slow-moving/low-stock (`getLowStockItems`), via inventory services.

### 3.13 CFO & forecasting
- `cfoReport.service` (monthly CFO pack, cron 08:30), 13-week cash flow (`thirteenWeekCashFlow`), forecasting suite (LSTM/ETS/ensemble with drift + governance).

### 3.14 Templates & export — `/reports/templates*`, `/reports/export`
- Custom report templates (`ReportTemplate`), preview, render, export (PDF/Excel via `pdfExport`/`excelExport` utils).

## 4. Business rules

| ID | Rule |
|---|---|
| RP-01 | No report stores independent financial state; all derive from journals. |
| RP-02 | Reports read via the effective-lines stage (compound-entry safe). |
| RP-03 | Every report ties back to the ledger (VE-8…VE-12). |
| RP-04 | Cache is invalidated on every write; no stale totals survive a write cycle. |
| RP-05 | Historical reports reproduce historical values exactly (immutable rates). |
| RP-06 | Reports are tenant-scoped and paginated where list-like. |

## 5. Acceptance criteria

- [ ] Trial Balance columns are equal on any dataset.
- [ ] Balance Sheet balances; Assets == Liabilities + Equity.
- [ ] P&L net income equals ledger revenue − expense.
- [ ] Aging buckets sum to AR/AP control-account balances.
- [ ] A write immediately reflects in the next report read (cache invalidated).
- [ ] A historical-date report is unchanged by later transactions.

## 6. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Report ≠ ledger | Stored/duplicated state | RP-01 derive-only |
| Stale totals | Missing cache invalidation | RP-04; write-path invalidate |
| Compound entry mis-summed | Reading only the pair | Effective-lines stage (RP-02) |
| Slow statements at volume | Per-row app loops | Aggregation `$group` + cache |

## 7. Regression requirements

Report changes ship with a reconciliation test (report vs ledger) and a cache-invalidation test. Never "fix" a report by hard-coding an adjustment; fix the source query or the underlying entry.

## 8. Implementation guidance

Compose new reports in `reportBuilder.service` using the effective-lines aggregation; add the route to `report.routes.js`; add a reconciliation check to the Validation Engine (VE-N). Export via the shared PDF/Excel utils.

## 9. Performance notes

Aggregation pipelines with `businessId`-leading indexes; `reportCache` for repeat views; pagination on ledger/aging lists; `.lean()` reads. Heavy CFO/forecast packs run on cron and cache their output. See [11_PERFORMANCE_AND_SCALABILITY.md](./11_PERFORMANCE_AND_SCALABILITY.md).

## 10. Security notes

Reports expose financial totals — gated by auth + business context + RBAC. Export endpoints stream files without leaking cross-tenant data. Narrative/AI reports are grounded in the tenant's own figures only.

## 11. Future expansion

Consolidated multi-entity reports (once multi-book exists), drill-down from any figure to its journals, scheduled report delivery (`scheduledReport.job` exists), and per-jurisdiction statutory formats.

## 12. Cross references

[01](./01_ACCOUNTING_ENGINE_SPECIFICATION.md) · [06_VALIDATION_ENGINE.md](./06_VALIDATION_ENGINE.md) · [11_PERFORMANCE_AND_SCALABILITY.md](./11_PERFORMANCE_AND_SCALABILITY.md)

## 13. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from real report routes/services; ties each report to a VE reconcile check. |

## 14. Progress checklist

- [x] Core statements documented (TB, GL, P&L, BS, CF)
- [x] AR/AP aging, tax, statements, KPIs, templates
- [x] Reconciliation mapping to Validation Engine
- [ ] Drill-down + consolidated reporting (future)
