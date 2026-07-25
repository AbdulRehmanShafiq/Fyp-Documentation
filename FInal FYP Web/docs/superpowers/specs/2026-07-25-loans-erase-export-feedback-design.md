# Design — Loans receivable, transaction erase, transaction export, feedback detail

**Date:** 2026-07-25
**Status:** Approved for implementation
**Scope:** backend (`vousfin-backend-main`) + frontend (`vousfin-frontend-main`)

Four independent fixes, shippable in any order. Each has its own section, its own
tests and its own risk profile. Feature 2 is the only one that touches core
accounting doctrine and it is the only one that needs a doctrine exception.

---

## Feature 1 — Money you lent out (non-trade receivable)

### The problem

Recording "gave 1250 to Ali Raza as a loan" produces a journal entry with no
counterparty and no open item. Nothing appears in Receivables and there is no
per-person balance.

Two root causes:

1. `TRANSACTION_TYPES.LOAN_DISBURSEMENT` (`config/constants.js:365`) means *money
   we borrowed* — `importAccountResolver.js:132` credits a non-current Liability.
   There is no type for money we lent.
2. `openItem.service.resolveOpenItem` (`services/openItem.service.js:177`) admits
   an item as a receivable **only** when `transactionType === 'Credit Sale'`.
   Anything else is rejected with "Allocations must target a credit sale
   (invoice) or credit purchase (bill)".

### Accounting decision

A loan to a person is a **non-trade receivable**. It is a different balance-sheet
line from trade AR and must never post to account 1110.

This is not a stylistic preference. `openItem.sumOpenLedger` is what
`ledgerIntegrity.computeArApSubledgerDrift` (invariants VE-5/VE-6) compares
against the AR control account. Putting a loan into the AR open-items union while
its debit sits in a different account makes that reconcile drift by the loan
amount, permanently, on every loan.

**Therefore: loans get their own control accounts and their own sub-ledger.**

| Party kind | Control account |
|---|---|
| `employee` | 1165 `Employee Loans & Advances` (already a default) |
| everything else | **1145 `Loans & Advances to Others`** (new default) |

1145 is added to `DEFAULT_ACCOUNTS`. `accountRepository.syncMissingDefaults`
already runs on every `GET /business/accounts`, so every existing business
receives it with no migration.

### New transaction types

```js
LOAN_ISSUED:            'Money Lent',              // we lent money out (asset ↑)
LOAN_REPAYMENT_RECEIVED:'Loan Repayment Received', // they paid us back (asset ↓)
```

Deliberately distinct from the existing `LOAN_REPAYMENT` ('Loan Repayment'),
which means *we* repaid a bank. Both new types join `NON_TAXABLE_TYPES` in
`transaction.service.js:295` — lending money is not a supply, so no GST/VAT/WHT.

### Journal shape

Lending 1250 to Ali Raza:

```
DR  1145 Loans & Advances to Others   1250
CR  1010 Cash at Bank                 1250
```

The entry carries `customerId` (the party), `remainingBalance = 1250`,
`paymentStatus = 'unpaid'`, optional `dueDate`, `transactionType = 'Money Lent'`.
It is **journal authority** in the open-item model (`isProjection` is false, there
is no document) — the simple, already-exercised path.

Repayment goes through the **existing settlement engine**
(`transaction.recordPartialPayment`), not a new one:

```
DR  1010 Cash at Bank        500
CR  1145 Loans & Advances    500
```

`remainingBalance` drops to 750, `paymentStatus` becomes `partially_paid`,
`settlements[]` records it. One engine, no special path.

**Interest is out of scope for v1.** If the business charges interest it records
it as a separate income entry. Explicitly not modelled — no accrual schedule, no
amortisation. (`InstallmentPlan` already exists for structured repayment and is
not touched here.)

### The person

`Customer.model.js` gains two fields:

```js
partyKind: { type: String, enum: ['customer','employee','individual','other'],
             default: 'customer', index: true },
currentLoanBalance: { type: Number, default: 0, min: 0 },
```

`partyKind` defaults to `customer`, so every existing record keeps its current
behaviour and every existing query keeps working.

`currentLoanBalance` is **separate from `currentReceivableBalance` on purpose**.
`currentReceivableBalance` drives the credit-limit check and
`Customer.getTopDebtors`. Folding loan balances into it would silently block
sales on a credit limit consumed by an unrelated personal loan, and would
misreport top debtors. Two numbers, two owners, no mixing.

### Open-item authority

`openItem.service` learns a third direction, `'loan'`:

- `resolveOpenItem` accepts `LOAN_ISSUED` → `{ direction: 'loan', partyType: 'party',
  authority: 'journal' }`. Loans are never document-authority; a projection loan
  is a contradiction and is refused.
- `openItems(businessId, 'loan')` returns loan rows via a new
  `transaction.repository.getOutstandingLoans(businessId)`, shaped exactly like
  the existing outstanding rows so the Receivables UI reads them unchanged.
- `sumOpenLedger(businessId, 'loan', { byControlAccount: true })` returns totals
  **grouped by control account**, because 1145 and 1165 reconcile separately.

`_sideCfg` gains a `loan` branch. The existing `receivable` / `payable` branches
are not modified — no behaviour change for trade AR/AP.

### Integrity

A sixth invariant joins `ledgerIntegrity.service`:

> **VE-7 — loan sub-ledger.** For each loan control account (1145, 1165), the sum
> of open loan items posting to it equals that account's journal-derived balance.

Surfaced through `booksAssurance` and `GET /reports/books-assurance` like the
other five. `scripts/ledgerDrift.js` must still read 0 after any loan is posted.

### Frontend

- **Receivables page** (`src/pages/parties/ReceivablesPage.jsx` + `MobileOutstanding.jsx`):
  a second section "Loans & advances" below "Customer invoices", with its own
  total and aging. Trade AR section is unchanged.
- **Transaction entry**: a "Money lent to someone" type that asks for the person
  (party picker, inline-create) and an optional due date.
- **NL entry**: a `loan_issued` intent so "gave 1250 loan to Ali Raza" parses
  correctly. `nlParserPreview.helper.js:57` maps intents to types; add the new
  mapping and a golden case in `scripts/eval/golden/nl-parse.golden.json`.
- **Excel import**: `excelParser.utils.js` keyword rules gain `lent to`,
  `loan given`, `advance to` → `Money Lent`.

### Existing data

The user's current 1250 entry needs no migration script. Once Feature 2 ships it
is erased and re-entered correctly. Writing a migration for a single
mis-categorised entry would be more risk than the fix.

### Tests

Normal flow (lend → appears in loan open items with the party attached) ·
repayment settles through the shared engine · partial repayment · trade AR total
is unchanged by a loan (the regression this design exists to prevent) ·
`currentReceivableBalance` untouched, `currentLoanBalance` moved ·
VE-7 holds after lend and after repay · drift 0 · employee loans route to 1165 ·
`syncMissingDefaults` backfills 1145 idempotently.

---

## Feature 2 — Erase a transaction, permanently

### The doctrine exception

`CLAUDE.md` states: *"Never delete Journal Entries"* and *"Financial history is
permanent."* This feature is a **deliberate, bounded exception**, approved by the
product owner on 2026-07-25.

The exception is narrow and the boundary is what makes it safe:

- The entry is removed from the live ledger, but a **complete frozen snapshot is
  preserved** in an append-only archive. History is not destroyed; it is moved
  out of the books.
- Erase is only permitted where the entry has **no accounting consequences yet** —
  nothing settled it, nothing references it, no period closed over it, no tax
  return reported it. In that state, removing it and reversing it produce the
  identical ledger; erase merely also removes the two confusing rows.
- Anything with consequences **must** still be reversed. The gate refuses, names
  the blocker in plain words, and offers reversal.

The existing `DELETE /transactions/:id` (`transaction.controller.js:1126`) is a
misnamed reverse. It is left exactly as it is — callers depend on it. Erase is a
new, separately-permissioned route.

### Archive

New model `ErasedJournalEntry`:

```js
{
  businessId, originalEntryId,
  snapshot,            // the complete JournalEntry document, verbatim
  journalLines,        // the effective lines that were reversed out
  balancesBefore,      // [{ accountId, accountCode, runningBalance }]
  balancesAfter,
  erasedBy, erasedByName, erasedAt, reason, ipAddress,
}
```

Append-only: no update or delete path is written for it, ever. Readable by
`AUDIT_MANAGE` holders only.

### The eligibility gate — fails closed

`transaction.service.eraseTransaction(id, businessId, { reason }, userId, ip)`.
Refuses (409, plain-language message naming the blocker) when **any** of:

| Blocker | Check |
|---|---|
| Period closed or locked | `AccountingPeriod.findCoveringPeriod(businessId, entry.transactionDate)` status is `closed`/`locked`. **No admin override** — unlike posting, there is no `PERIOD_OVERRIDE` escape hatch for erase. |
| Payment applied | `partiallyPaidAmount > 0` or `settlements[]` non-empty |
| Already reversed | `status === JOURNAL_STATUS.REVERSED`, or another entry exists with `reversalOf === this._id` (there is no `reversedBy` field — the link lives on the reversal) |
| Is itself a reversal | `reversalOf` set |
| Is a document projection | `isProjection === true` or `projectionOf.documentId` set |
| System-generated | `transactionSource === 'system_generated'` — fix these at their source |
| Referenced by a document | reverse lookup across `Invoice`, `Bill`, `Payment`, `GoodsReceipt`, `PurchaseOrder`, `CreditNote`, `VendorCredit`, `PayrollRun`, `InstallmentPlan`, `FixedAsset`, `StockMovement`, `BankStatement` for this entry id |
| Referenced by another entry | any `JournalEntry` with `parentTransactionId` = this id, `reversalOf` = this id, or `relatedTransactions.transactionId` = this id |
| Tax return filed | a `TaxReturn` in `filed` state whose period covers `transactionDate` |
| Inventory effect | `inventoryItemId` set, or a `StockMovement` links to it |

A blocker list, not a first-failure abort: the response names **every** reason so
the user does not fix one and hit the next.

### The erase itself

Entirely inside one `withTransaction` (`utils/withTransaction.js`):

1. Re-read the entry **inside the session** and re-run the gate (a payment could
   have landed between the check and the write).
2. Snapshot `balancesBefore` for every affected account.
3. **Insert the archive record first.** If the archive write fails, nothing else
   has happened.
4. For each effective line, apply the exact inverse running-balance delta via
   `accountRepository.updateRunningBalance(accountId, -delta, session)`, using the
   same debit/credit-vs-`normalBalance` rule as
   `ledgerPosting.applyRunningBalance` (`services/ledgerPosting.service.js:81`).
   Read lines through the same `journalLines`-first rule as
   `EFFECTIVE_LINES_STAGE` so compound entries are exact.
5. Roll back cached party balances (`Customer.currentReceivableBalance` /
   `currentLoanBalance`, `Vendor` equivalent) for the amount this entry moved.
6. `JournalEntry.deleteOne({ _id, businessId }, { session })`.
7. `auditService.log` with the full before-state and the reason.
8. Emit an `erased` business event.
9. **Verify before commit:** run `ledgerIntegrity.computeDrift(businessId)` inside
   the session. Non-zero drift throws → the whole transaction rolls back → the
   entry is still there and nothing changed. The erase can only commit if the
   books are provably still square.

Step 9 is the load-bearing safety property. Everything else is defence in depth.

### Permission and route

- New `PERMISSIONS.TRANSACTION_ERASE = 'transaction:erase'`. `ROLE_PERMISSIONS`
  is untouched: `owner: ['*']` grants it, and `accountant` — whose list is
  explicit — does not. Owner-only by default with no extra wiring.
- `DELETE /api/v1/transactions/:id/erase`, guarded by
  `requirePermission(TRANSACTION_ERASE)`. Body: `{ reason }` (required,
  10–500 chars).
- `GET /api/v1/transactions/erased` — the archive list, `AUDIT_MANAGE` only.

### Frontend

`TransactionDetailModal.jsx` gains a danger action "Erase permanently",
visible only to permitted roles (`Can.jsx`). Confirming requires typing a reason.
Copy is plain, per the product-copy rule — "This entry will be removed from your
books completely. A copy is kept for audit. This cannot be undone." When the gate
refuses, the blockers render as a plain list with "Reverse it instead" as the
offered next step.

### Tests

The eligibility matrix, one test per blocker · balance rollback is exact for
2-line and compound entries · drift is 0 after erase · the archive record exists
and matches the erased entry · a concurrent payment loses the race and the erase
rolls back · closed-period refusal has no override · non-owner is refused ·
erasing does not disturb any other entry's balance · the legacy `DELETE /:id`
still reverses exactly as before (regression).

---

## Feature 3 — Export transactions

### Endpoint

`GET /api/v1/transactions/export?format=csv|xlsx&<same filters as the list>`

The query schema **extends `transactionFiltersSchema`**
(`validations/transaction.validation.js:261`) rather than defining its own, so
what the list shows is exactly what the export contains. `page`/`limit` are
dropped and replaced by a hard row cap (50 000) that returns a clear message
asking for a narrower date range rather than silently truncating.

Server-side by design. The existing `ui/ExportButton.jsx` builds a CSV from
whatever rows are already in the browser — i.e. the current page only — which is
not what "export all transactions for a period" means. That component is left in
place for the pages that use it.

### Sheet 1 — "Transactions" (one row per entry)

Date · Entry ID · Reference / Invoice No · Description · Type · Debit account
(code + name) · Credit account (code + name) · Amount · Currency · Exchange rate ·
Base amount · Party (customer or vendor) · Payment status · Remaining balance ·
Tax amount · Cost centre · Source (manual / AI / import / system) · Entered by ·
Entered at · Status.

Entries touching more than two accounts show `-- Split --` in both account
columns; their full detail lives in Sheet 2.

### Sheet 2 — "Ledger lines" (one row per debit/credit)

Date · Entry ID · Line # · Account code · Account name · Debit · Credit ·
Description · Cost centre. Ends with a totals row proving Σ debit = Σ credit.

Read through `transaction.repository.EFFECTIVE_LINES_STAGE` so compound entries
are exact and the file ties to the trial balance.

### Format

- **xlsx** via `exceljs`, reusing the header/style helpers already in
  `utils/excelExport.utils.js` (`addDocHeader`, `addColHeaders`, `applyBorders`).
  Real date and number types, both sheets, a document header carrying business
  name, period covered, base currency and generation timestamp.
- **csv** — Sheet 1's columns only (CSV has no second sheet). The response names
  this in a header comment row so nobody mistakes it for the full ledger.

### Frontend

An Export control on `TransactionsList.jsx` (and `MobileTransactions.jsx`) with a
date-range preset (this month / last month / this year / custom), format choice,
and a note that it exports everything matching the current filters, not just the
visible page.

### Tests

Filters are honoured identically to the list endpoint · a compound entry renders
as `-- Split --` in Sheet 1 and in full in Sheet 2 · Sheet 2 totals balance ·
foreign-currency rows carry both original and base amounts · the row cap returns
a clear error rather than a truncated file · tenant isolation (another business's
entries never appear) · empty result produces a valid file with headers.

---

## Feature 4 — Feedback is readable

### Bugs found

In `src/pages/admin/AdminPage.jsx`:

1. **Line 570** — malformed JSX: ``className={`inline-flex>`` never closes the
   template literal before the ternary, so the status badge receives a garbage
   className and renders unstyled.
2. **Line 597** — the admin-note `<textarea>`'s `onChange` sets `confirm` state,
   which opens the `ConfirmDialog`. A confirmation dialog fires on **every
   keystroke**, making the note box unusable.
3. **Line 565** — Submitter reads `f.userId?.email`, but
   `userFeedback.service.listAll` (`services/userFeedback.service.js:29`) never
   populates `userId`. It is a raw ObjectId, so the column always shows "—".
4. **Line 553** — the message is the whole point of feedback and it is clamped to
   two lines in a 200px-wide cell with no way to see the rest.

### Backend

- `listAll` populates `userId` with `fullName email`, and `businessId` with
  `businessName`.
- New `GET /api/v1/admin/feedback/:id` → `adminController.getFeedback` →
  `userFeedbackService.getById(id)`, returning the populated document. 404 when
  absent.

### Frontend

New `src/components/modals/FeedbackDetailModal.jsx`, modelled on the existing
`TransactionDetailModal.jsx` and built on `modals/Modal.jsx` (which already
renders as a bottom sheet on mobile, so mobile comes free).

Contents: subject · type badge · rating · full message with line breaks preserved
and its own scroll · submitter name and email · business · submitted date ·
status dropdown · admin note textarea with local state and an explicit **Save**
button.

The whole table row becomes clickable (plus `role="button"`, `tabIndex`, and
Enter/Space handling so it is keyboard-reachable). Row-level controls stop
propagation so changing status inline still works. The three bugs above are
fixed in the same pass; the Submitter column falls back to
`f.userId?.email || f.email || f.name || '—'`.

### Tests

Detail modal renders the complete message · clicking a row opens it · keyboard
activation opens it · saving a note calls the API once, not per keystroke ·
submitter falls back correctly when `userId` is null (anonymous feedback) ·
the status badge gets a real className.

---

## Sequencing

Independent; recommended order:

1. **Feature 4** — smallest, pure bug-fix, zero accounting risk.
2. **Feature 3** — additive read-only endpoint, no writes.
3. **Feature 1** — additive accounting, new invariant.
4. **Feature 2** — highest risk, benefits from Feature 1 being settled first.

Every feature is TDD, and `scripts/ledgerDrift.js` must read 0 after Features 1
and 2.
