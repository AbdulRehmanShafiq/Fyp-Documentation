# Accounting Correctness by Construction — Design (2026-07-15)

## The thesis

VousFin's accounting engine is architecturally right and measurably healthy. What
it lacks is not accounting — it is **enforcement**.

Measured baseline (verified live, not assumed):

| Check | Result |
|---|---|
| Trial balance | balances exactly (Dr = Cr = 221,902,399) |
| Balance-sheet equation | holds, difference 0 |
| Ledger drift (4 businesses) | 0, all journals balanced |
| Inventory sub-ledger drift | 0 |
| Audit 2026-07-02 findings F1–F17 | all genuinely closed |

Notice **why** those four are healthy: each is enforced *inside* a chokepoint
nothing can go around. `postCompoundJournal` refuses an unbalanced journal, so no
journal is unbalanced — anywhere, ever.

Now notice the failures. Every finding in this audit — and every finding in the
two audits before it — is the same bug wearing a different hat:

> **A correctness rule exists, but nothing forces you to use it.**

Balanced journals are enforced in the poster → drift is 0.
Idempotency, fail-closed recognition, and read-the-authority are *conventions* →
each has been violated somewhere, silently, for months.

**So this program adds no accounting features.** It moves existing rules from
convention into places they cannot be bypassed, and proves them against a real
database.

---

## Findings

### G1 — Core recognition fails open (P0, latent)

`invoice.service.postArJournal` abandons AR **and revenue** recognition with a
`logger.warn` and `return null` on three conditions (missing 1110; no revenue
account; debit == credit). The invoice is still approved. `bill.service` does the
same for AP (2110). `journalGenerator` skips realised FX. `fiscalYear
._runClosingEntries` skips year-end close — and `closeFiscalYear` then marks the
year `CLOSED` **anyway**, with `retainedEarningsTransferred: 0`.

The sharpest evidence that this is an oversight rather than a decision:
`_applyCogsForInvoice`, in the *same file*, was deliberately fixed (INV-5) to
resolve accounts **before** touching stock and fail **closed**. So on a missing
revenue account today, one half of an invoice posts COGS and relieves stock while
the other half silently recognises no revenue. Audit F10/F11 fixed precisely this
class for tax and FX-rate; the sweep never reached AR, AP, or close.

Retained Earnings is resolved by **name regex** (`/retained earnings/i`) with no
`accountCode: '3210'` fallback — while the clearing account in the same function
correctly tries code `3310` first. Renaming an account silently disables year-end
close, permanently.

**Status: latent, not firing.** The live business has every required account
(1110, 2110, 3210, 3310, 4110, 1150, 5110 all present). It is one rename away.

### G2 — Idempotency is opt-in; 14 of 22 posting services opted out (P1)

F7 built the mechanism correctly — partial unique index `idx_je_idempotency_key`,
E11000 translated to an idempotent return. But the poster reads
`if (idempotencyKey)`: **no key means no protection at all**, and the partial
index only binds when the key is a string.

Keyless: `accountingPeriod` (6 posts), `invoice` (6), `arApVoidCredit` (5),
`creditNote` (4), `fiscalYear` (4), `inventoryAdjustment` (4), `recognitionSchedule`
(3), `vendorCredit` (3), `payment` (2), `assembly`, `earlyPaymentDiscount`,
`impairment`, `inventoryRecalc`, `jobCosting`.

Any retry — network, double-click, cron re-run, driver retry — double-posts.
Year-end close is in this group.

### G3 — No test has ever touched a real database (P0 for verification)

This is the root cause of the audit→fix→audit cycle.

- No `mongodb-memory-server` anywhere in the repo.
- 7 of 8 "integration" tests mock persistence.
- `tests/setup.js` points `MONGO_URI` at a local mongo that is not running.

**All 2,074 tests pass without executing a single real aggregation, index,
transaction, or hook.** Every report pipeline (`EFFECTIVE_LINES_STAGE`, income
statement, cash flow, aging, valuation) is unverified. That is why F1 hid behind
1,786 green tests, and why the aging defect below hid behind 2,030. The 5 GRN
suites that currently fail are the *only* ones reaching for real Mongo; they time
out.

### G4 — Reports re-derive truth instead of reading the authority (P1)

Fixed today, same class, found by live verification rather than tests:

1. `getStockLedger` returned movement type but not `direction`, so the client
   regexed `/purchase/i` to guess in-vs-out → every non-purchase inflow rendered
   as an outflow.
2. `aging()` valued age bands at each receipt's **original** cost while its own
   `value` column used **current carrying** cost → after a revaluation one line
   reported 96,000 across bands and 92,000 in total, and disagreed with valuation.
   It also read `currentStock`/`unitCostPrice` (a cached projection) where
   `valuationAsOf` replays the sub-ledger — a second source of truth.

Same family as F1 and F15. Still open: `getAccountTurnover` reads top-level pairs.

### G5 — Non-atomic composites (P1)

`_runClosingEntries` posts outside the transaction that flips `FiscalYear.status`.
Entries can post while the year stays open → close again → double closing entries.

### G6 — Open P3 debt (from 2026-07-02)

Dead `transactionRepository.bulkCreate` (raw `insertMany`, skips hooks);
locked-period override dead code; `checkImmutability` allows `transactionDate`
moves; party-balance updates keyed by `_id` without `businessId`; dual-write
mirror failures warn-only; `markPaid` doc/JE divergence; `settlements[]` unbounded.

---

## Design

### Decisions taken

**On failure to resolve an account → self-heal, then refuse.** Resolve by code →
by role → seed the missing default → only then refuse, in plain language. This
generalises the deterministic resolve-or-create chain that already fixed the
bulk-import Owner-Equity bug. An owner must never see an error for something the
system can fix itself. Refusal is the last resort, not the first.

**Sequence: harness before fixes.** Every later fix becomes provable instead of
hopeful, and the harness retro-catches the bug class that mocks structurally
cannot see.

### Phase 0 — The proof harness

`mongodb-memory-server` **in replica-set mode** (required: `withTransaction` and
sessions need a replica set). New `tests/live/` tier executing the real pipelines.

Centrepiece: a **Golden Invariants** assertion, run after any operation —

1. Trial balance balances (Σ debits = Σ credits)
2. Balance-sheet equation holds (A = L + E)
3. Ledger drift is 0 (cached running balances = journal-derived)
4. Sub-ledgers reconcile to their control accounts (AR, AP, inventory)

Any new accounting operation is run through it. This is the regression net F1,
F15, and the aging defect all slipped through. It also repairs the 5 GRN suites.

### Phase 1 — One self-healing account resolver

`services/accountResolver.service.js`. One chain, used by everything:

```
resolve by accountCode (authoritative)
  → else by role / accountSubtype
  → else seed from DEFAULT_ACCOUNTS (idempotent, like syncMissingDefaults)
  → else throw ApiError, plain language
```

Replaces five competing idioms: name-regex (`fiscalYear`), bare `findOne` by code
(`invoice`/`bill`), `$in` fallback lists, `resolveCostAccounts`, `ensureTaxAccounts`.
That scatter *is* the fail-open surface; collapsing it removes the surface.

### Phase 2 — Recognition fails closed

With the resolver underneath, delete the `return null` warn-skips in
`postArJournal`, bill AP, `_runClosingEntries`, and realised FX. `_applyCogsForInvoice`
already fails closed; this makes the other half of the same invoice agree.

`closeFiscalYear` must not mark a year `CLOSED` when no closing entry posted.

### Phase 3 — Idempotency mandatory at the poster

Make `idempotencyKey` a **required** payload field on `postCompoundJournal` /
`postBalancedJournal` — throw when absent. Give each keyless service a natural
key: `close:{fyId}`, `invoice-ar:{invoiceId}`, `credit-apply:{creditId}:{invoiceId}`.

Enforcing at the poster is what makes it unbypassable — the same reason the
balance rule never fails.

### Phase 4 — Atomicity + derived-not-stored sweep

Year-end close (entries **and** status flip) into one `withTransaction`.
`getAccountTurnover` → effective lines. P3 debt: delete dead `bulkCreate`, scope
party-balance updates by `businessId`.

### Phase 5 — Continuous assurance

Promote Golden Invariants from a test into an always-on monitor, extending the
existing integrity gate and `closeReadiness` agent. The product claim becomes
*"your books are provably correct as of 14:32"* — or the exact break, in plain
language, with a self-heal offered where safe.

### Explicitly out of scope

- New accounting features. They exist and largely work; features are not the gap.
- Unrelated refactoring.
- The `sent`/`approved` invoice carrying no AR journal (INV-202607-24893). Every
  account it needed exists, so G1 did not cause it — it is a state-machine
  question, tracked separately.

---

## Testing

Each phase lands TDD, red→green, and must leave: full suite green, ledger drift 0,
Golden Invariants passing. Phase 0's harness is what makes the rest meaningful —
before it, "green tests" was not evidence of accounting correctness, and twice
demonstrably wasn't.

## Risk

The behaviour change is Phase 2: paths that silently skipped now refuse. Phase 1
lands first precisely so that refusal is rare — the resolver heals the common
cases (missing/renamed default) before refusal is ever reached.

---

## Implementation status (2026-07-15, same session)

### Phase 0 — SHIPPED (`84a09a2`)

`tests/live` on mongodb-memory-server in replica-set mode; Golden Invariants
delegating to the production integrity services. 34 live tests green.

**It found seven declared indexes that mongod silently rejected — so they never
existed, in test OR production.** Mongoose builds indexes lazily against a live
connection, and no test had one:

| Model | Index | Fault |
|---|---|---|
| JournalEntry | `idx_tax_report` | sparse + partialFilterExpression |
| JournalEntry | `idx_je_invoice_number` | sparse + partial (**UNIQUE**) |
| InventoryItem | barcode | sparse + `$ne` (**UNIQUE**) |
| InventoryItem | sku | `$ne` in partial (**UNIQUE**) |
| Customer | email | `$ne` in partial (**UNIQUE**) |
| Vendor | email | `$ne` in partial (**UNIQUE**) |
| PayrollRun | businessId+period | `$ne` in partial (**UNIQUE**) |

Five were unique constraints protecting nothing: duplicate invoice numbers, SKUs,
barcodes, customer/vendor emails and **two live payroll runs for one period** were
all silently possible. mongod accepts only equality, `$exists:true`, `$gt/$gte/
$lt/$lte`, `$type`, `$in` and top-level `$and`; it rejects every negation and
refuses to mix `sparse` with `partialFilterExpression`. Live data checked before
landing — no duplicates exist, so the constraints enable without repair.
`tests/live/indexes.live.test.js` keeps the class from returning.

### Phases 1 + 2 — SHIPPED for close and FX (`8f05fdf`, `4629c82`)

`accountResolver.service` landed. Year-end close fixed on four counts (rename-proof
resolution by code, self-heal, `fy-close:{fyId}` idempotency key, entries + status
flip in one transaction, and the A8-violating "any Revenue account" fallback
deleted). Realised FX no longer skips when 4140/6200 are absent.

Three bugs the live tier caught that mocks could not — all the same shape, code
assuming it could read outside its own transaction:

- `resolveMany` used `Promise.all` on a shared session; a ClientSession allows
  only one operation in flight and mongod rejected the second.
- The poster's tenant guard and `applyRunningBalance` both read WITHOUT the
  session, so an account healed earlier in the same transaction looked foreign /
  missing and blew up the posting.

Full suite: 2110 passing (was 2069). Drift 0.

### Implementation COMPLETE (2026-07-16)

Every phase in this spec has shipped. Backend: **301 suites / 2139 tests, zero
failures**; drift 0; all four live businesses report "Your books add up."

| Phase | Status |
|---|---|
| 0 — real-DB proof harness + Golden Invariants | ✅ shipped (`84a09a2`) |
| 1 — self-healing account resolver | ✅ shipped (`8f05fdf`) |
| 2 — recognition fails closed (close, FX, **AR/AP**) | ✅ shipped (`8f05fdf`, `4629c82`, `77a61a3`) |
| 3 — idempotency mandatory at the poster | ✅ shipped (`d111ec8`) |
| 4 — atomicity + derived-not-stored sweep | ✅ shipped (`75810ec` + this pass) |
| 5 — continuous assurance | ✅ shipped (`9bbbdd4`) + `GET /reports/books-assurance` |

**AR/AP fail-open — closed.** `postArJournal` / `postApLiabilityJournal` now
resolve by code through the resolver, which seeds a missing default; the
`return null` skips are gone. Two things the resolver exposed on the way:

- Bill's expense fallback asked for `5100 → 5000 → 6100` and **none of those
  exist in DEFAULT_ACCOUNTS** — for any standard business the chain always
  resolved to null and skipped the payable. Hidden only because bill lines
  normally carry an explicit account. Now falls back to Miscellaneous Expenses
  (6390): the honest answer to "we were not told which expense", visible for the
  owner to recategorise. Booking the payable to Miscellaneous beats not booking it.
- Revenue pointed at the AR control account is NOT healable (the entry would
  cancel itself out), so it refuses in plain language naming the fix.

**A production break the live tier caught (`77a61a3`).** Routing every invoice
through `postArJournal` for the first time exposed that **seven** system posting
sites omitted `inputMethod`, which the schema REQUIRES — every one would have
thrown. It hid because the invoice-first flow was unreachable (transaction-first
invoices short-circuit on `linkedJournalEntryId`; below-threshold ones
early-returned) and because the unit tests mock the poster, so no schema ever ran.
Defaulted in `postCompoundJournal` rather than at seven call sites — same
reasoning as the balance rule.

**Phase 3's shape, corrected by contact with the code.** "Mandatory" cannot mean
"every posting has a key": builds, stock adjustments, revaluations, recalcs and
period adjusting entries are repeatable ON PURPOSE, and an entity-derived key
would block the second legitimate one. So the poster demands a *decision*:

    a string  → happens once; the DB enforces it
    null      → deliberately repeatable; I decided
    undefined → you forgot. Throw.

Retry-safety for the repeatable ones belongs at the API boundary as a
caller-supplied request key — the one piece deliberately left for later.

**Phase 4 was already largely closed** by the concurrent session: `getAccountTurnover`
deleted outright (an unused helper modelling the wrong pattern is a trap, and
deleting beats fixing), party balances tenant-scoped, dead `bulkCreate` removed.
Locked-period override resolved as recommended: never overridable on LOCKED,
`forcePost` on CLOSED.

**The 5 GRN failures were never environmental** — twice assumed so, wrongly.
Standard costing made GRN receipt read `InventoryItem`; neither suite mocked it,
so they hit the real model with no database and hung until Mongoose's 10s
buffering timeout. That timeout is a race, which is why the count wandered
between 5/6/8 and read as flakiness. `grnBillLifecycle`: 34s → 1.4s.

### ⚠️ Open — needs a decision, not code

**2 unposted invoices in live production, Rs 88,500.** INV-202607-24893 (43,500,
`sent`) and INV-202607-24895 (45,000, `approved`) — both below the 50,000
threshold, the bug's exact fingerprint. The fix stops new ones; these two are
still revenue and AR absent from the books. Repair means re-triggering
recognition per document or a backfill. Production data is not mutated without
asking. Bills: 0 affected.

Also deliberately deferred: an HTTP `Idempotency-Key` boundary for the repeatable
postings, and a frontend surface for `GET /reports/books-assurance`.

### Root cause of the unposted invoice — found (concurrent session)

`invoice.service.submitForApproval` auto-promotes a below-threshold invoice to
`approved` and **returns early**, never posting AR, revenue, COGS or stock. With
the 50,000 default threshold that is the *normal* case — which is exactly why
INV-202607-24893 (43,500) sat `sent`/`approved` with no journal. Recognition now
runs through one `_recognizeApprovedInvoice` shared by both doors into `approved`.
This was the *cause*; G1's fail-open is a separate, still-latent hazard.
