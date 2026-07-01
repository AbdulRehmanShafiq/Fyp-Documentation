# 01 — Accounting Engine Specification

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Journal rules, Chart of Accounts, posting mechanics, tax, FX, drift |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> The accounting engine is the single authority that converts **business events** into **balanced journal entries**. Modules describe events; they do not invent accounting. This document specifies the rules the engine enforces and cites the code that enforces them.

---

## 1. Purpose & scope

**Purpose.** Define the double-entry rules, account model, posting mechanics, tax handling, foreign-currency treatment, period control, reversal mechanics, and integrity verification that all ledger activity must obey.

**Scope.** `services/transaction.service.js`, `services/ledgerPosting.service.js`, `services/journalGenerator.service.js`, `services/taxEngine.service.js`, `services/ledgerIntegrity.service.js`, `services/partyBalance.service.js`, `models/JournalEntry.model.js`, `models/ChartOfAccount.model.js`, `models/AccountingPeriod.model.js`, `config/constants.js`. Out of scope: report presentation (Doc 09), per-transaction narratives (Doc 04).

## 2. Definitions

| Term | Meaning |
|---|---|
| **Journal Entry (JE)** | An immutable, balanced accounting record. The authoritative ledger unit (`JournalEntry`). |
| **Journal Lines** | `JournalEntry.journalLines[]` — the authoritative multi-leg debit/credit effect. The top-level `debit/creditAccountId` + `amount` triple is a **derived denormalized projection** for indexes/back-compat, never the truth. |
| **Chart of Accounts (CoA)** | The account master (`ChartOfAccount`), 82 seeded defaults per business. |
| **Running balance** | `ChartOfAccount.runningBalance` — a **cached** signed accumulator, reproducible from journals. |
| **Control account** | An account summarizing a subsystem (AR 1110, AP 2110, tax payables). Flagged `isControlAccount`; metadata for reporting/reconciliation (see §4.4). |
| **Posting** | Persisting a balanced JE and applying per-line running-balance deltas atomically. |
| **Drift** | `cached − journal-derived` balance for an account. MUST be 0. |
| **Poster** | `postCompoundJournal` (system, N-line) or `postBalancedJournal` (2-line shim), or the human-entry `createTransaction`. |

## 3. Core philosophy

```
Business event  →  Accounting Engine  →  Balanced Journal Entry  →  Derived reports
```

Rules: every event once; every entry balances; reports derive from entries; corrections via new entries; never overwrite history. These realize Master Plan invariants I1–I10.

## 4. Chart of Accounts

### 4.1 Numbering scheme

Ranges seeded by `DEFAULT_ACCOUNTS` (`config/constants.js`, 82 accounts):

| Range | Class | Normal balance |
|---|---|---|
| 1000–1099 | Assets — Bank & Cash | Debit |
| 1100–1199 | Assets — Current | Debit |
| 1200–1299 | Assets — Non-current (incl. contra 1250, 1267 = Credit) | Debit/Credit |
| 2100–2199 | Liabilities — Current | Credit |
| 2200–2299 | Liabilities — Non-current | Credit |
| 3100–3399 | Equity (drawings 3120 = Debit) | Credit/Debit |
| 4100–4299 | Revenue (returns 4115 = Debit) | Credit/Debit |
| 5100–5199 | Direct cost (COGS) | Debit |
| 6100–6499 | Operating expenses | Debit |
| 1170–1177, 2121–2130 | Tax engine accounts (lazily seeded per country) | Debit/Credit |

Full account list: `config/constants.js` `DEFAULT_ACCOUNTS`. Representative anchors: 1010 Cash at Bank, 1110 Accounts Receivable, 1150 Inventory, 2110 Accounts Payable, 2115 Goods Received Not Invoiced, 2120 GST Payable, 2125 WHT Payable, 3210 Retained Earnings, 3310 Current Year Earnings, 4110 Sales, 4140 FX Gain, 5110 COGS, 6200 FX Loss, 6230 Depreciation, 6370 Bad Debt.

### 4.2 Schema (owned by Doc 02, summarized here)

`ChartOfAccount`: `businessId`, `accountName` (unique/business), `accountType` (Asset/Liability/Equity/Revenue/Expense), `accountSubtype`, `accountCode` (unique/business, sparse), `parentAccountId` (reserved for hierarchy), `isControlAccount`, `normalBalance` (Debit/Credit), `isDefault`, `runningBalance` (signed).

### 4.3 Seeding & backfill

- New business → `bulkCreateDefaultAccounts()` seeds all 82.
- `accountRepository.syncMissingDefaults(businessId)` is additive-idempotent (keyed on `accountCode`); called on every `GET /business/accounts`. It also **backfills** `isControlAccount:true` onto AR/AP/tax codes for pre-flag businesses.
- Tax accounts (1170–1177, 2121–2130) are created lazily by `taxEngine.ensureTaxAccounts()` when a business enables tax, flagged `isControlAccount:true`.

### 4.4 Control accounts — policy

`CONTROL_ACCOUNT_CODES = ['1110','2110','2120','2125','2145','2198']` plus the tax-engine dynamic range (`isTaxEngineControlCode`). The flag is **metadata only** — it is NOT a posting block.

> **Design decision (2026-07-01).** A blanket "block direct posting to control accounts" rule was designed and **rejected** after verifying against `accountFilterRules.js`: `Credit Sale` debits AR directly, `Payment Received` credits AR directly, `Credit Purchase`/`Payment Made` touch AP, `GST/WHT Payment` touch tax payables — all first-class everyday transaction types. VousFin has no per-customer AR/AP sub-ledger (reconciliation is via `partyBalanceService`), so a hard block would break core flows. The flag exists for report grouping and a future AR/AP-to-control reconciliation check, not to reject posts. See [08_EDGE_CASE_LIBRARY.md](./08_EDGE_CASE_LIBRARY.md) EC-CONTROL-01.

## 5. Double-entry rules

For every posted JE:

- **R1 Balance.** Σ(line.amount where type=debit) == Σ(line.amount where type=credit), rounded to 2 dp. Enforced in `createTransaction` and `postCompoundJournal`.
- **R2 Minimum legs.** ≥ 2 lines. Compound entries (3+ lines) are first-class.
- **R3 Distinct 2-line.** On the derived pair, `debitAccountId ≠ creditAccountId` (schema validator).
- **R4 Positive amounts.** Each line amount > 0; the headline `amount` is finite, positive, ≤ 999,999,999,999 (input hardening).
- **R5 Signed running balance.** Debit-normal accounts increase on debit; credit-normal increase on credit. `_updateAccountBalance` applies the signed delta.

### Accounting equation

Assets = Liabilities + Equity holds continuously because every entry is balanced and posts atomically (I9). A background balance-equation check (FR-02.1) re-verifies after writes.

## 6. Posting mechanics

Two canonical posters plus the human-entry path. **Never** `JournalEntry.create()` raw when balances are affected.

### 6.1 `ledgerPosting.postCompoundJournal(payload, {updateBalances, session})`

Canonical system poster. Validates ≥2 lines, positive amounts, lowercase `debit/credit` type, Σdebit=Σcredit. Derives the back-compat pair (first debit, first credit, Σdebits). Unifies idempotency on `metadata.idempotencyKey` (returns the existing entry if the key already posted). Persists the JE and calls `applyRunningBalance` per line, all inside `withTransaction` (or the caller's session). No tax/FX/inference enrichment — the caller supplies exact lines. Used by payroll (one compound entry per run), fixed-asset depreciation, GRNI accrual, FX gain/loss, invoice/bill projections.

### 6.2 `ledgerPosting.postBalancedJournal(entry, opts)`

Thin 2-account shim over `postCompoundJournal`; honours a supplied compound `journalLines`.

### 6.3 `transaction.service.createTransaction(data, userId, ip, session?)`

The **human/AI-entry** path. Does full enrichment (auto-tax, FX, type inference, AR/AP detection, COGS/stock mirror, double-submit guard) then persists `journalLines` on every non-FX entry inside `withTransaction`. Idempotency keyed on the top-level `idempotencyKey`. This is the single funnel for form, NL, Excel batch, bank reconciliation, installments, recurring, and AI auto-post. Full 12-stage sequence: [04_TRANSACTION_LIFECYCLE.md](./04_TRANSACTION_LIFECYCLE.md) §2.

### 6.4 Balance-update authority

Only two call sites mutate `runningBalance`: `transaction.service._updateAccountBalance` and `ledgerPosting.applyRunningBalance`, both via `accountRepository.updateRunningBalance` inside a session. `ledgerIntegrity` and repair scripts are the only other touch points and are reconciliation-only. Any `$inc` on a balance field elsewhere is a bug.

## 7. Tax engine (multi-country)

`services/taxEngine.service.js`. Countries: PK, AE, SA, IN, US, GB (`config/countryTaxProfiles.js`).

| Function | Responsibility |
|---|---|
| `getBusinessTaxConfig(businessId)` | Merge `business.taxConfig` with country profile. |
| `isTaxEnabled(businessId)` | True if any of gst/vat/wht enabled. |
| `resolveApplicableTaxes(opts)` | Compute applicable tax components (GST/VAT/WHT), inclusive/exclusive, reverse-charge, WHT schedule → `{lines,totalTax,netAmount,grossAmount,...}`. |
| `calculateTax(amount, component, mode)` | Pure inclusive/exclusive math → `{netAmount,taxAmount,grossAmount}`. |
| `generateTaxJournalLines(type, amount, taxResult, accountMap)` | Emit balanced tax legs (output tax on sales, input tax on purchases, WHT withheld, reverse-charge self-supply). |
| `ensureTaxAccounts(businessId, country)` | Lazily seed country tax accounts, `isControlAccount:true`. |

**Integrity guard (R-03).** Client-supplied `taxAmount` is clamped to within 1% or 5 minor units of the engine value — the engine is authoritative; forged client tax cannot post. Tax is skipped for closing/opening/adjusting/system entries and non-taxable types (transfers, financing, FX, depreciation).

Tax journal patterns (see Doc 04 for full worked entries): **Output (sale)** DR Cash/AR (gross) / CR Revenue (net) / CR GST Payable (tax). **Input (purchase)** DR Expense/Inventory (net) / DR GST Receivable (tax) / CR AP/Cash (gross). **WHT** DR Expense (net) / CR Cash (net−wht) / CR WHT Payable (wht). **Reverse charge** DR Input tax / CR Output tax (self-supply).

## 8. Foreign currency (IAS 21)

`services/journalGenerator.service.js` + FX fields on `JournalEntry`.

- Every FX transaction stores `currencyCode`, `exchangeRate`, `baseCurrencyAmount = amount × rate`. The ledger runs in base currency; balances update from `baseCurrencyAmount`. Historical rates are immutable (I8).
- **Realized FX (IAS 21 §28).** On settling a foreign AR/AP, `computeRealisedFx` derives the gain/loss from booking vs settlement rate. Gain → CR 4140 FX Gain; loss → DR 6200 FX Loss; the other leg is the AR/AP account. Posted via `postCompoundJournal`, idempotency `fx:realised:{parentId}:{settlementId|date}`, `transactionSource=system_generated`, `entryType=adjusting`.
- **Unrealized revaluation (IAS 21 §23a).** Month-end: for each open foreign AR/AP, `diff = foreign×closingRate − bookedBase`; post a revaluation entry (reversed next period to avoid double count). Direction: AR diff>0 → gain; AP diff>0 → loss.

## 9. Accounting periods & close

`models/AccountingPeriod.model.js`, `models/FiscalYear.model.js`, `services/accountingPeriod.service.js`, `services/closeAgent.service.js`.

- **Period status.** OPEN (normal), CLOSED (blocks non-system entries; reopenable with reason), LOCKED (permanent; super-admin override only).
- **Enforcement.** `JournalEntry.pre('save')` and update/delete hooks call the period lock; `createTransaction` and `reverseTransaction` re-check. `_isSystemCloseEntry` (closing/opening_balance + system-generated) may post into CLOSED.
- **Close process.** Period/year close snapshots totals, generates closing entries (temporary accounts → Retained Earnings) and opening-balance carry-forward; entries tagged `entryType=closing|opening_balance`, `closingBatchId`.

## 10. Reversal & correction

`transaction.service.reverseTransaction()`:

1. Load original with details; refuse if already REVERSED or has partial payments applied.
2. Period-lock both original date and reversal date.
3. Build a mirror entry: swap debit/credit accounts, flip every `journalLines[].type`, preserve amount/type, set `reversalOf = original._id`, `transactionSource = system_generated`.
4. Atomically post the reversal, update balances, roll back AR/AP party balances for credit sales/purchases, mark original `status=REVERSED`, store `metadata.reversalId`.
5. Cascade-cancel a linked installment plan; audit-log the reversal; invalidate report cache.

Adjusting entries (accruals, deferrals, depreciation) use `entryType=adjusting` and follow the same posting rules.

## 11. Integrity verification

`services/ledgerIntegrity.service.js` `computeDrift(businessId, asOf=ALL_TIME)`:

- For each account: `derived = normalBalance==Debit ? Σdebit−Σcredit : Σcredit−Σdebit` over BALANCE_STATUSES (posted, partially_settled, settled, reversed). `drift = cached − derived`.
- Returns `{balanced, totalDebits, totalCredits, driftedCount, totalAbsDrift, accounts[]}`.
- `scripts/ledgerDrift.js` reports read-only (MUST print 0); `scripts/recomputeLedgerBalances.js` repairs (dry-run default, snapshot before `--apply`, refuses if journal unbalanced, re-verifies drift→0).

Run after any ledger-touching change. Non-zero drift indicates a crash mid-post, an out-of-band balance edit, or a sign bug.

## 12. Business rules (catalog)

| ID | Rule |
|---|---|
| AE-01 | A JE persists only if balanced (R1). |
| AE-02 | `journalLines[]` is authoritative; the top-level pair is derived. |
| AE-03 | Running balance is derived; drift MUST be 0. |
| AE-04 | Posted financial fields are immutable; corrections via reversal. |
| AE-05 | No write into LOCKED; no non-system write into CLOSED. |
| AE-06 | Tax engine is authoritative over client tax (R-03 clamp). |
| AE-07 | Historical FX rate/base amount never overwritten. |
| AE-08 | AR/AP treatment follows the **account pair**, not the type label. |
| AE-09 | Inventory sale auto-posts COGS (DR 5110 / CR 1150) in the same entry. |
| AE-10 | Every posting path funnels through a canonical poster; no raw creates. |

## 13. Acceptance criteria

- [ ] Posting an unbalanced payload is rejected with a 4xx and nothing persists.
- [ ] A compound (3+ line) entry posts and each line's running balance updates atomically.
- [ ] `computeDrift` returns `balanced:true, totalAbsDrift:0` after a representative transaction set.
- [ ] Editing a posted JE's amount is rejected by the immutability hook.
- [ ] A reversal nets the original to zero effect (drift unchanged, original marked reversed).
- [ ] Tax on a GST sale produces DR AR (gross)/CR Revenue (net)/CR GST Payable (tax) and balances.
- [ ] Settling a foreign AR at a changed rate posts a realized FX gain/loss that balances.
- [ ] A write into a LOCKED period is rejected (423/403).

## 14. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Trial balance drift | Crash after JE create, before balance update | `withTransaction` atomicity (I9); drift gate |
| Double post | Retried request without idempotency | `metadata.idempotencyKey`; double-submit guard |
| Wrong AR/AP classification | Trusting type label over accounts | Account-pair detection (AE-08) |
| Forged client tax | UI supplies inflated tax | R-03 clamp |
| History rewrite | Direct model update | Immutability hook (AE-04) |
| FX distortion | Overwriting historical rate | Rate immutability (AE-07) |

## 15. Regression requirements

Any change here MUST ship with tests covering: balanced-vs-unbalanced posting, compound-entry balances, reversal netting, tax journal shape, FX realized gain/loss, period-lock rejection, and idempotent retry. The drift script MUST read 0. See [10_TESTING_STRATEGY.md](./10_TESTING_STRATEGY.md).

## 16. Implementation guidance

- To add a new transaction type: define the type in `TRANSACTION_TYPES`, add the journal template/inference, add tax applicability if relevant, and add a lifecycle entry in Doc 04 + tests. Do not add a bespoke posting path.
- To add a country's taxes: extend `countryTaxProfiles.js` (`taxes`, `additionalAccounts`); `ensureTaxAccounts` seeds them. No engine code change.
- To add a compound system entry (e.g., a new accrual): call `postCompoundJournal` with exact lines and a stable idempotency key.

## 17. Performance notes

Posting is O(lines) with per-line indexed balance `$inc`. Reports never recompute balances on the write path. Hot read paths use `reportCache` (Doc 11). On Atlas M0, concurrent writes to the same account can WriteConflict; bulk import uses bounded concurrency + a sequential recovery pass (Doc 04 §Excel).

## 18. Security notes

Every posting is tenant-scoped and audit-logged (who/when/ip/before/after). Journal-line account IDs are validated to belong to the tenant (prevents cross-tenant balance corruption). Control-account and approval gates are independent layers (Doc 12).

## 19. Future expansion

Multi-book/consolidation, deferred-revenue schedules as first-class, per-jurisdiction e-invoicing, and configurable journal templates per industry — all as additive layers emitting events into this engine (Master Plan §10).

## 20. Cross references

- Pipeline stages & per-transaction entries → [04_TRANSACTION_LIFECYCLE.md](./04_TRANSACTION_LIFECYCLE.md)
- Schema/index detail → [02_DATABASE_ARCHITECTURE.md](./02_DATABASE_ARCHITECTURE.md)
- Drift/validation harness → [06_VALIDATION_ENGINE.md](./06_VALIDATION_ENGINE.md)
- Reports derived from ledger → [09_REPORTING_ENGINE.md](./09_REPORTING_ENGINE.md)

## 21. Revision history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-07 (draft) | Generic template. Superseded. |
| 2.0.0 | 2026-07-01 | Rewritten from audit: real posters, tax/FX functions, control-account decision, drift definition, acceptance criteria. |

## 22. Progress checklist

- [x] CoA numbering + seeding documented
- [x] Posting mechanics (both posters + human path)
- [x] Tax engine functions + R-03 guard
- [x] FX realized/unrealized (IAS 21)
- [x] Period control + reversal
- [x] Drift definition + gate
- [ ] Per-industry journal-template configurability (future)
