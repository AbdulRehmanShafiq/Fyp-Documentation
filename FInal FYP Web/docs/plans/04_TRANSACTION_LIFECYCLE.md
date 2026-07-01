# 04 — Transaction Lifecycle

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Per-transaction end-to-end behaviour (trigger → validation → journal → downstream) |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> Every financial event, regardless of entry channel, traverses **one** pipeline and produces **one** balanced accounting story. This document specifies the pipeline and catalogs each transaction type's journal effect and downstream consequences.

---

## 1. Purpose & scope

Define (a) the Universal Transaction Pipeline every posting traverses, and (b) for each business transaction, its trigger, validation, journal entries, inventory/tax/AR-AP effects, downstream propagation, rollback, and failure modes. Accounting rules are owned by [01](./01_ACCOUNTING_ENGINE_SPECIFICATION.md); entity shapes by [03](./03_BUSINESS_DOMAIN_MODEL.md).

## 2. The Universal Transaction Pipeline

Implemented in `services/transaction.service.js` `createTransaction()`. Ordered stages (line anchors approximate):

| # | Stage | What happens |
|---|---|---|
| 0 | Multi-line derivation + input hardening | Derive top-level pair from `journalLines`; coerce amounts finite/positive/≤1e12; normalize line types; parse date. |
| 1 | Core validation | Required fields; amount>0; debit≠credit. |
| 1b | Idempotency guard | If `idempotencyKey` already posted, return existing entry. |
| 1c | Double-submit guard | UI-form only: reject identical entry within 10s. |
| 2 | Account validation | Accounts belong to tenant; every `journalLines[].accountId` tenant-checked. |
| 2c | Cost-centre validation | Entry/line `costCenterId` must be active. |
| 2b | FX enrichment | Resolve `exchangeRate`, compute `baseCurrencyAmount`. |
| 3 | Type inference | Infer `transactionType` from account pair if omitted. |
| 3c | Tax calculation | Engine computes tax; R-03 clamp on client tax; emits tax lines. |
| 3d | Document numbering | Atomic INV-/BILL- number for sales/purchases. |
| 4 | Party resolution | Find/auto-create customer/vendor by name. |
| 4.5 | Period lock check | Reject write into LOCKED / non-system into CLOSED. |
| 5 | Entry assembly | Build `entryData` (status POSTED, actor, period, tax metadata). |
| 6/7 | AR/AP detection | Account pair drives credit-sale/credit-purchase; adjust party balance. |
| 7/7a | Inventory mirror | Sale → COGS lines + `reduceStock`; purchase → `applyPurchaseStock`. |
| 7b | Merge tax + balance check | Append tax lines; assert Σdebit=Σcredit. |
| 8 | **Atomic persist** | `withTransaction`: create JE + per-line `updateRunningBalance`. |
| 9 | Audit + cache | `auditService.logCreate`; invalidate `reportCache`. |
| 10 | Document mirror | Sync Invoice/Bill projection if applicable. |
| 11 | Event emission | Emit `TRANSACTION_CREATED` (fire-and-forget) → subscribers. |

```mermaid
flowchart LR
  V[Validate] --> N[Normalize] --> C[Classify] --> BR[Business rules]
  BR --> AR[Accounting rules] --> J[Journal gen] --> PR[Projections]
  PR --> EV[Events] --> RR[Report refresh] --> AI[AI update] --> AU[Audit] --> CA[Cache]
```

**Invariant.** No module bypasses this flow. System multi-account entries use `ledgerPosting.postCompoundJournal` (payroll, depreciation, GRNI, FX, invoice/bill projection), which shares the atomic-persist + balance-update core.

## 3. Entry channels → pipeline

| Channel | Entry point | Notes |
|---|---|---|
| Manual form | `createFormTransaction` → `approval.submitOrPost` → `createTransaction` | `doubleSubmitGuard` on. |
| Natural language | `processNaturalLanguage` (preview) → `confirmNaturalLanguage` → `submitOrPost` | ≥98% + exact match + opt-in → auto-post; else preview/confirm; <95% → clarifying question. |
| Excel import | `uploadExcelPreview` → `confirmExcelImport` → `batchPosting.postBatch` | Per-row confidence gate (High import / Medium flag / Low hold-back); concurrent pass + sequential recovery. |
| AI auto-post | `submitOrPost` with `transactionSource=ai_auto_posted` | Amount-threshold approval still applies. |
| Bank reconciliation | `bankReconciliation.service` → `createTransaction` | `transactionSource=bank_reconciliation`. |
| Recurring | `transactionTemplate.generateDueRecurring` → `submitOrPost` | Cron 05:30. |
| Installments | `installment.service` → `createTransaction` | Parent + EMI + settlement. |
| Payroll | `payroll.service` → `postCompoundJournal` | One compound entry per run. |
| Procurement | invoice/bill/GRN services → `postBalancedJournal`/`postCompoundJournal` | AR/AP + GRNI. |
| Reversal | `reverseTransaction` | Mirror entry, `transactionSource=system_generated`. |

## 4. Approval & auto-post gates (independent layers)

`approval.submitOrPost` evaluates the **amount threshold** (`Business.approvalSettings`): above threshold → park `PendingTransaction` (nothing posts); below → post now. The **AI confidence** gate (auto-post) is separate: even a 100%-confidence parse of a large amount still parks for approval. Approval **re-runs the full pipeline** on the stored payload — never a raw replay.

## 5. Transaction catalog

Notation: each entry lists Debit / Credit legs. Accounts by common name (code).

### 5.1 Sales & revenue

| Transaction | Journal | AR/Inventory/Tax | Reversal |
|---|---|---|---|
| **Cash Sale** | DR Cash (1010) / CR Sales (4110) [+ CR GST Payable (2120) if tax] | — | Mirror reversal |
| **Credit Sale** | DR Accounts Receivable (1110) / CR Sales (4110) [+ tax] | AR +; `paymentStatus=UNPAID`, `remainingBalance` set | Reversal rolls back AR |
| **Inventory Sale** | Sale legs **plus** DR COGS (5110) / CR Inventory (1150) at unit cost | `reduceStock`; COGS in same entry | Reversal restores stock effect via new entry |
| **Payment Received** | DR Cash (1010) / CR Accounts Receivable (1110) | Settles invoice; AR −; `partiallyPaidAmount`/`settlements[]` | Void payment reverses settlement |
| **Advance from Customer** | DR Cash (1010) / CR Advance from Customers (2190) | Liability until earned | Reversal |
| **Refund (customer)** | DR Customer Refunds/Sales Returns / CR Cash | — | Reversal |

### 5.2 Purchases & expenses

| Transaction | Journal | AP/Inventory/Tax | Reversal |
|---|---|---|---|
| **Cash Purchase** | DR Expense / CR Cash (1010) [+ DR GST Receivable if input tax] | — | Reversal |
| **Credit Purchase** | DR Expense/Asset / CR Accounts Payable (2110) [+ tax] | AP +; UNPAID | Rolls back AP |
| **Inventory Purchase** | DR Inventory (1150) / CR Cash or AP | `applyPurchaseStock` (weighted-avg/FIFO) | Reversal |
| **Payment Made** | DR Accounts Payable (2110) / CR Cash (1010) | Settles bill; AP − | Void reverses settlement |
| **Prepaid Expense** | DR Prepaid Expenses (1120) / CR Cash | Amortized later via adjusting entry | Reversal |

### 5.3 Procurement (PO → GRN → Bill)

| Step | Journal | Effect |
|---|---|---|
| Purchase Order approved | none (commitment only) | `quantityReceived=0` |
| Goods Receipt confirmed | DR Inventory (1150) / CR Goods Received Not Invoiced (2115) | Stock in; GRNI accrual; `inventoryApplied` guard |
| Bill approved (3-way matched) | DR GRNI (2115) [+ DR GST Receivable] / CR Accounts Payable (2110) [− WHT] | Clears GRNI; AP liability; WHT withheld to 2125 |

Three-way match within ±5% tolerance; mismatch blocks bill posting.

### 5.4 Payments, credits, adjustments

| Transaction | Journal |
|---|---|
| **Credit Note (AR)** | DR Sales Returns/Revenue [+ DR GST Payable] / CR Accounts Receivable (1110) |
| **Vendor Credit (AP)** | DR Accounts Payable (2110) / CR relevant expense/inventory |
| **Overpayment (advance)** | DR Cash / CR Advance liability (held as `unappliedAmount`) |
| **Journal Entry (manual)** | Arbitrary balanced lines; `entryType=normal` |
| **Adjusting Entry** | Accrual/deferral/depreciation; `entryType=adjusting` |

### 5.5 Payroll

One compound entry per run (`postCompoundJournal`):
```
DR Wages and Salaries (6180)                 = gross
  CR Salary Tax Withheld Payable (2141)      = income tax withheld
  CR EOBI/Social Security Payable (2142)     = EOBI employee
  CR Provident Fund Payable (2143)           = PF employee
  CR Cash/Bank (1010)                        = net pay
```
Employer contributions (EOBI/PF/WWF) post additional expense/liability legs. Reversible; one live run per period.

### 5.6 Assets & financing

| Transaction | Journal |
|---|---|
| **Asset Purchase** | DR Fixed Asset (12xx) / CR Cash or AP |
| **Depreciation** | DR Depreciation Expense (6230) / CR Accumulated Depreciation (1250) |
| **Asset Disposal** | DR Cash + DR Accumulated Depreciation / CR Asset + CR/DR Gain(4220)/Loss(6490) |
| **Loan Disbursement** | DR Cash / CR Loan Payable (2230) |
| **Loan/Installment Repayment** | DR Loan Payable + DR Interest Expense (6240) / CR Cash (interest→principal waterfall) |
| **Lease (IFRS 16)** | DR Right-of-Use Asset (1269) / CR Finance Lease Liability (2245) |

### 5.7 Tax

| Transaction | Journal |
|---|---|
| **GST/VAT Collection** | CR GST Payable (2120) / VAT Payable (2198) on sales |
| **Input tax** | DR GST Receivable (1170) on purchases |
| **WHT Deduction** | CR WHT Payable (2125) withheld at source |
| **GST/WHT Payment (remit)** | DR tax payable / CR Cash |
| **Reverse charge** | DR Input tax / CR Output tax (self-supply) |

### 5.8 Period-end & FX

| Transaction | Journal |
|---|---|
| **Realized FX gain/loss** | AR/AP leg / FX Gain (4140) or FX Loss (6200) on settlement |
| **Unrealized FX revaluation** | Revaluation leg vs AR/AP (reversed next period) |
| **Closing entry (year-end)** | Temporary accounts → Retained Earnings (3210); `entryType=closing` |
| **Opening balance (new FY)** | Carry-forward balances; `entryType=opening_balance` |

## 6. Bulk Excel import (detailed)

`confirmExcelImport` → `batchPosting.postBatch`:
1. Partition rows by confidence label: **High** import; **Medium** import + `metadata.needsSpotCheck` + counted `flagged`; **Low** held back into `failed[]` with a clear reason (picked up by the CSV export of unrecorded rows).
2. Post accepted rows through the approval gate (`submitOrPost` → `createTransaction`) with bounded concurrency (`BATCH_POST_CONCURRENCY`, default 8).
3. **Sequential recovery pass:** rows that failed concurrently (mostly Atlas WriteConflicts on the same account) are retried single-threaded with a stable idempotency key (`sha256(businessId:batchId:index)`), so conflict-losers succeed and cannot double-post.
4. Response reports `successful / pending / flagged / failed[]`. The frontend surfaces failures and offers a downloadable CSV of unrecorded rows for correction and re-import.

## 7. Downstream propagation (the "after works")

After the JE persists, in one request cycle:
- `reportCache` invalidated (statements re-derive on next read).
- `businessEvents.emit(TRANSACTION_CREATED)` → `eventSubscribers`: analytics cache invalidation, RAG reindex (debounced ~5 min), AR/AP aging refresh, party-balance events. Fire-and-forget so a subscriber error can never unbalance or roll back the ledger (Master Plan I9).
- Invoice/Bill projection synced if the entry mirrors a document.
- Balance-equation check (Assets = L + E) scheduled (FR-02.1); health indicators re-evaluated.

## 8. Rollback semantics

Nothing is hard-deleted. Corrections:
- **Reversal** (`reverseTransaction`): mirror entry, original marked REVERSED, AR/AP rolled back, installment plan cancelled, audited.
- **Void** (documents): posts reversing GL entries, sets `voidedAt`, records `voidJournalEntryIds`.
- **Refused reversal:** if the entry has partial payments applied or the period is LOCKED.

## 9. Business rules

| ID | Rule |
|---|---|
| TL-01 | Every channel funnels into the pipeline; no side-door posting. |
| TL-02 | AR/AP treatment follows the account pair, not the type label. |
| TL-03 | Inventory sale auto-posts COGS in the same entry. |
| TL-04 | Approval (amount) and auto-post (confidence) are independent gates. |
| TL-05 | Approval re-runs full validation, not a raw replay. |
| TL-06 | Low-confidence Excel rows are never silently posted. |
| TL-07 | Downstream subscribers are fire-and-forget; they cannot roll back the ledger. |

## 10. Acceptance criteria

- [ ] Each cataloged transaction posts a balanced entry matching the documented legs.
- [ ] Inventory sale reduces stock and posts COGS atomically with the revenue entry.
- [ ] GRN confirm posts GRNI; bill approval clears it; net AP is correct.
- [ ] Excel import of mixed-confidence rows imports High, flags Medium, holds Low.
- [ ] A parked pending transaction posts identically to a direct post when approved.
- [ ] Reversing any transaction leaves drift = 0.

## 11. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Silent skipped rows | Confidence/WriteConflict not surfaced | Recovery pass + failed[] + CSV export |
| Double post on retry | Missing idempotency | Idempotency keys everywhere |
| COGS/revenue split across entries | Non-atomic mirror | Same-entry COGS + `withTransaction` |
| Approval replay drift | Raw payload replay | Re-run pipeline on approve |

## 12. Regression requirements

Adding/altering a transaction type ships with: a balanced-JE test asserting the exact legs, an inventory/tax/AR-AP side-effect test where relevant, a reversal test, and a drift check. See [10_TESTING_STRATEGY.md](./10_TESTING_STRATEGY.md).

## 13. Implementation guidance

Never add a bespoke posting path. Extend inference/tax/template logic inside the pipeline, register events for new downstream needs, and document the new type here with its legs before coding.

## 14. Performance / 15. Security notes

Bounded-concurrency batch posting; per-line indexed balance updates; fire-and-forget events keep the write path short (Doc 11). Every post is tenant-scoped, audited, and account-tenant-validated (Doc 12).

## 16. Future expansion

New verticals emit events consumed here; new document types mirror the PO→GRN→Bill pattern; configurable journal templates per industry (Doc 01 §19).

## 17. Cross references

[01](./01_ACCOUNTING_ENGINE_SPECIFICATION.md) · [03](./03_BUSINESS_DOMAIN_MODEL.md) · [08_EDGE_CASE_LIBRARY.md](./08_EDGE_CASE_LIBRARY.md) · [09_REPORTING_ENGINE.md](./09_REPORTING_ENGINE.md)

## 18. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from pipeline + service audit; full journal catalog with real account codes. |

## 19. Progress checklist

- [x] Universal pipeline stages
- [x] All entry channels mapped
- [x] Transaction catalog with journal legs
- [x] Excel import + recovery pass
- [x] Downstream propagation + rollback
- [ ] Per-country tax-leg appendix (future)
