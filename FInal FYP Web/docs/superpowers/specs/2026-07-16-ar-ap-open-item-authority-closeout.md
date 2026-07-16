# AR/AP Open-Item Authority — Correctness Closeout Spec

**Date:** 2026-07-16
**Status:** DESIGN — approved for implementation, nothing implemented yet
**Prerequisite reading:** `vousfin-backend-main/docs/ar-ap-domain-refactor.md` (the M-refactor),
`docs/superpowers/specs/2026-07-15-accounting-correctness-by-construction-design.md` (the parent program)

---

## 0. What this spec is

One implementation plan that resolves **every accounting-correctness issue currently open
in VousFin**, with the explicit constraint that **no new issue, bug, or regression may
arise from it**. Each phase is independently shippable, gated on the full test suite,
the live-DB tier, `scripts/ledgerDrift.js` = 0, and booksAssurance all-green — the same
gates the parent program used.

The lens is the parent program's thesis, which explained every finding here too:

> **A correctness rule exists, but nothing forces you to use it.**

The M-refactor ratified "the document is the source of truth; the JE is its immutable
projection" — and then built only *half* the readers and *none* of the settlement path
onto that rule. The rule was opt-in. This spec moves it into a chokepoint.

---

## 1. Issue register

### 1.1 Open — fixed by this spec

| # | Issue | Evidence | Impact |
|---|---|---|---|
| **I-1 (P1)** | Invoice-first AR/AP recognition posts a projection JE (`isProjection: true`, `remainingBalance: null`) but **every open-item reader/writer only understands JE-authority**. | `invoice.service.js:736` (postArJournal), `bill.service.js:680` (postApLiabilityJournal); readers below | Invoice-first invoices/bills **cannot be settled by a payment** (`payment.service.js:302` rejects `remainingBalance == null`; `transaction.service.js:1022` same); **invisible to hub aging** (`report.service.js:866`) and to `/transactions/outstanding` (`transaction.service.js:1705` → JE-only repo queries); **permanent AR/AP sub-ledger drift** (`ledgerIntegrity.service.js:162` sums only `JE.remainingBalance`). Live proof: business FinTech Solutions, customer Ali Raza — cached 4,500 vs open JEs 2,000; INV-202607-24894 posted 2,500 with `rem null` → drift 2,500, confirmed by both `scripts/ledgerDrift.js` and booksAssurance check 4. |
| **I-2** | Two parallel AR/AP reporting worlds. M7 built the document-based read model (`arApReporting.service.js` — "documents are truth, ledger is verification") but the hub aging report, `/transactions/outstanding`, and the drift reconciler still read the JE-only view. The two views disagree whenever either convention posts. | `arApReporting.service.js:1-30` vs `report.service.js:860-914` | Same business, two different aging totals depending on which page you open. Competing sources of truth — the exact thing CLAUDE.md forbids. |
| **I-3** | Output-tax leg of invoice-first recognition is **fail-open**: if no 2120/2125 account exists, `outputTaxAcc` stays null and the tax JE is silently skipped. | `invoice.service.js:789-796` | AR debited net-only while the document owes total-with-tax → reconciler drift by exactly the tax; tax liability never booked; tax report understates. Same class as F11, which was fixed on the transaction path but not here. Bill-side input-tax leg must be audited for the symmetric hole. |
| **I-4** | `markPaid` on a **transaction-first** invoice/bill flips the document to `paid` without touching the JE open item, the party balance, or posting a settlement. | `invoice.service.js:650` (`if (invoice.arJournalId …) else` plain state change), `bill.service.js:517` | Document says paid; aging, payment engine and reconciler still see the full balance open. Doc/JE divergence in the *opposite* direction from I-1. |
| **I-5** | `markPaid` on an **invoice-first** doc settles correctly but creates **no Payment record** and guesses the cash account from a hardcoded `$in` list. | `invoice.service.js:974-1014` | Payments list is incomplete for audit; cash resolution is a name/code guess (`1010/1020/1040/1030`). |
| **I-6** | Dual-write mirror (`JE → Invoice/Bill` on credit sales/purchases) is **warn-only**. | `transaction.service.js:919-925` | A credit sale can exist in the ledger with no document. Invariant 5 (everything recorded) reads documents → a missing mirror is invisible to it; M7's doc view under-reports. |
| **I-7** | `checkImmutability` does not restrict `transactionDate` moves on **posted** entries within open periods. | `JournalEntry.model.js:841` (`transactionDate` absent from `restrictedFields`); `checkPeriodLock` only blocks moves *into* closed/locked periods (`:822-828`) | A posted entry can silently migrate between open months — monthly statements rewrite with no reversal and no audit annotation. |
| **I-8** | `settlements[]` grows unboundedly on hot AR/AP journal entries; settlement events have no first-class home. | `JournalEntry.model.js:168`; appended on every partial payment | Document bloat on the hottest entries; the authoritative record of "what settled what" is smeared across JE subdocs and `Payment.allocations`. |
| **I-9** | Remaining name-regex / `$in`-list account resolution sites bypass `accountResolver` (the parent program's chokepoint). | `invoice.service.js:564-572` (write-off: 6370/1110 by regex), `creditNote.service.js:352-356` (debit-note apply: 1110/4110 by regex), `invoice.service.js:977-982` (settlement cash `$in` guess), I-3's tax lookup | The scatter *was* the fail-open surface the resolver exists to close. These sites fail closed (they throw) but don't self-heal and re-model the pattern the program deleted. |
| **I-10** | Live production data: AR drift 2,500 (I-1's live instance) and 2 unposted invoices worth Rs 88,500 (root cause already fixed; user ruled the account is test data — repair optional). | booksAssurance + ledgerDrift, 2026-07-16 | Drift self-heals when I-1 lands (see §6.2 — verify, don't assume). Unposted invoices get an optional idempotent recognizer script. |

### 1.2 Already closed — verified against HEAD this session (do not re-open)

- Debit-note GL posting exists and goes through the poster with `debit-note-apply:{id}` idempotency (`creditNote.service.js:358+`).
- Credit notes / vendor credits / write-off / early-payment discount all adjust **both** the document and (via `openItem.adjustOpenItem`, F3) the JE open item; `adjustOpenItem` safely no-ops on projections.
- Locked-period override, `bulkCreate`, `getAccountTurnover`, party-balance tenant scoping — all closed in the parent program's Phase 4.
- F1–F17 (core-engine audit), A1–A14/T1/T3 (codebase audit), HTTP `Idempotency-Key` boundary, booksAssurance UI chip — all shipped.
- Period locks already allow settlement-metadata-only updates (F9 allowlist) — Phase 2 builds on this, no change needed.

---

## 2. The decision: authority-per-item (Option B), through one chokepoint

### 2.1 Why not Option A (dual-write `remainingBalance` onto the projection JE)

- Contradicts the ratified M-refactor ("the JE is generated, **never the master**").
- Re-creates the split-brain the M-refactor exists to kill: two writable copies of the same money, kept equal by discipline — the exact bug class (`re-derived instead of read the authority`) found twice in the inventory program.
- The projection JE's `amount` is the **net** (revenue leg); the open item is the **total incl. tax**. Storing `remainingBalance > amount` on one entry is a standing lie that every future reader must know about.

### 2.2 Why not "full M9 now" (document is the open item for *everything*)

Transaction-first open items include populations with **no document at all**: installment
plans, manual credit-sale/purchase journals (`payment.service.js:311-314` explicitly
supports settling unlinked entries), and legacy JE-only data. Full retirement would mean
minting synthetic documents for all of them plus migrating every open JE — a huge,
risky migration to fix a bug that doesn't require it. Full M9 stays the end-state
direction; it is explicitly **out of scope** here.

### 2.3 The rule (Option B, made unbypassable)

> Every AR/AP open item has **exactly one authority**, decided by an airtight
> discriminator, and **every** reader and writer resolves it through **one module**.

- **Discriminator:** `JE.isProjection === true` ⟺ the linked document owns the money
  (document authority). Otherwise the JE owns it (journal authority — all existing
  transaction-first behavior, byte-for-byte unchanged).
  Document-side equivalent: `Invoice.arJournalId != null` / `Bill.apLiabilityJournalId != null`
  (only `postArJournal`/`postApLiabilityJournal` ever set these; the transaction-first
  sync path sets only `linkedJournalEntryId`).
- **Chokepoint:** `services/openItem.service.js` grows from "credit adjuster" into the
  **open-item authority layer**. Nothing else may decide which side owns a balance.

### 2.4 Unit discipline (F2 applies here too — spell it out)

- `JE.remainingBalance` is **base currency** (F2).
- `Invoice/Bill.remainingBalance` is **document currency**.
- The authority layer exposes **base** amounts everywhere (`remainingBase`), converting
  document-side balances at the document's booking rate, `r2`-rounded. Settlement of a
  document-authority item decrements the doc in **document units** (base ÷ booking rate,
  r2) while ledger/party moves stay base. Residual < 0.01 clears to zero/PAID.
  Every function signature in §3 states its unit. No exceptions.

---

## 3. Design — the open-item authority layer

All in `services/openItem.service.js` (existing module, existing F5 optimistic-guard
pattern). New exports; `adjustOpenItem` upgraded in place.

### 3.1 `resolveOpenItem(businessId, ref, { session }) → OpenItem`

`ref = { journalEntryId } | { documentType, documentId }`.

```
OpenItem {
  authority:   'document' | 'journal',
  direction:   'receivable' | 'payable',
  je,                          // the recognition JE (always present)
  doc,                         // Invoice/Bill (null only for journal-authority JE-only items)
  documentType, number,        // invoiceNumber/billNumber or JE ref
  partyId, partyType,
  dueDate,                     // doc.dueDate (document authority) | je.dueDate
  currencyCode, bookingRate,
  totalBase, paidBase, remainingBase,   // BASE currency, r2
}
```

Resolution rules (exhaustive; every branch fail-closed):
1. `journalEntryId` → load JE (tenant-scoped; 404 if absent).
   - `je.isProjection === true` → load `projectionOf.documentId`. **Document missing →
     REFUSE with a plain-language 500** ("this entry's source document is missing —
     contact support"): a projection without its document is corruption, never
     something to silently skip.
   - else → journal authority. `remainingBalance == null` → the existing 400
     ("does not track an outstanding balance"). Unchanged behavior.
2. `documentType + documentId` → load doc (tenant-scoped; 404 if absent).
   - invoice-first (`arJournalId`/`apLiabilityJournalId` set) → document authority.
   - else follow `linkedJournalEntryId` → rule 1. No linked JE → the existing 400.
3. Only `CREDIT_SALE`/`CREDIT_PURCHASE` recognition entries qualify (existing rule).

### 3.2 `openItemsPipeline(businessId, { direction, partyId? })` — THE one definition

The single aggregation both **reports** and the **reconciler** read, so they can never
disagree on what "open" means (the inventory program's aging-vs-valuation lesson):

```
journal side:  JournalEntry  { businessId, transactionType: CS|CP,
                               status ∈ OPEN_AR_AP_STATUSES,
                               isProjection: { $ne: true },
                               remainingBalance: { $gt: 0 } }
   UNION
document side: Invoice { businessId, isArchived ≠ true, arJournalId ≠ null,
                         state ∈ OPEN_AR_STATES, remainingBalance > 0 }
               (Bill symmetric, apLiabilityJournalId / OPEN_AP_STATES)
```

- Projections carry `remainingBalance: null`, so the journal side already excludes them;
  the explicit `isProjection` filter stays anyway — belt-and-braces plus a standing
  declaration that dual-writing rem onto projections is forbidden.
- Emits the same row shape the current outstanding/aging consumers use
  (`parentTransactionId` = the JE id **in both cases** — for document authority it is
  the projection JE — plus `documentId`, `number`, `dueDate`, `remainingBalance` in
  base, party fields). Additive only: existing response fields keep their names and
  meanings, so the frontend keeps working unchanged.
- Party-scoped sum variant `sumOpenByParty(businessId, direction)` feeds the reconciler.

### 3.3 `applySettlement(openItem, { baseAmount, session, source })` / `restoreSettlement(...)`

- **Journal authority:** delegates to the existing guarded JE update
  (`updateTransactionGuarded`, F5) — current code, moved not modified.
- **Document authority:** optimistic `findOneAndUpdate` on
  `{ _id, businessId, remainingBalance: <read doc-units value> }` →
  `paidAmount += docUnits`, `remainingBalance -= docUnits` (floor 0), state via
  `Invoice.canTransition` (`approved|sent|overdue → partially_paid → paid`; transitions
  verified present in `constants.js:694-707`). Lost race → the same 409 the F5 pattern
  throws. Never touches the projection JE's financial fields (immutability holds).
- `restoreSettlement` is the exact inverse (payment reversal path, F4).

### 3.4 `adjustOpenItem` (credits/write-offs) — upgraded, callers simplified

Today: adjusts the JE; no-ops on projections; callers *also* hand-write
`doc.remainingBalance` (`creditNote.service.js:190,195`). That is two writers for one
number. After: `adjustOpenItem` resolves authority and adjusts **the authority only**
(doc-side with the optimistic guard); callers stop mutating `remainingBalance` directly
(they keep their own fields: `totalCredited`, `creditNoteIds`, states). One writer per
number, same transaction, same guard.

---

## 4. Phases

Ordered so **readers converge before writers switch** — at every intermediate commit the
books are at least as correct as today. TDD throughout (red → green), every phase ends
with: full Jest suite green, `tests/live` green, `scripts/ledgerDrift.js` = 0 live,
booksAssurance all-green on all live businesses.

### Phase 1 — Authority layer + read convergence *(pure reads; zero write-path risk)*

1. Build §3.1/§3.2 with unit tests + a live suite (`openItem.authority.live.test.js`).
2. Converge every reader onto `openItemsPipeline` / `sumOpenByParty`:
   - `ledgerIntegrity.computeArApSubledgerDrift` (`:149`) — the sub-ledger sum becomes
     journal side + document side. booksAssurance check 4 inherits it (it delegates).
   - `report.service.getAgingReport` (`:860`) — rows from the pipeline; bucket logic
     untouched.
   - `transaction.getOutstandingBalances` (`:1705`) — union rows, same response shape.
   - `customerStatement` / vendor statements — same source.
   - `arApReporting` (M7) keeps its document-view role but its reconciliation summary
     reads the shared pipeline for the ledger side.
3. **New booksAssurance sub-check** (inside check 4, not a 6th headline): every
   `isProjection` JE's `projectionOf` document exists, and every invoice-first document's
   linked JE has `isProjection: true`. Corruption becomes visible the day it happens.
4. Live validation on production data: Ali Raza drift reads **0** with **zero data
   mutation** (2,000 JE-side + 2,500 doc-side = 4,500 cached — verify, don't assume;
   if it doesn't tie, stop and diagnose before Phase 2). INV-202607-24894 appears in
   aging and Receivables.

**Regression guard:** transaction-first rows come from the same queries as today
(filter added: `isProjection ≠ true`, which matches nothing today outside invoice-first
data). Golden test: pipeline output ≡ old query output on a seeded transaction-first-only
business, field for field.

### Phase 2 — Settlement through the authority *(the P1 fix)*

1. `payment.service._resolvePaymentData` resolves each allocation via `resolveOpenItem`;
   validates against `remainingBase` (per-JE accumulation logic unchanged, keyed per
   open item). The `remainingBalance == null` rejection now only fires for genuine
   non-open-item entries.
2. The apply loop (inside the existing single `withTransaction`, F14):
   - journal authority → existing `recordPartialPayment`, untouched.
   - document authority → new `_settleDocumentItem`: posts the settlement JE
     (DR cash / CR AR — AR from the projection JE's debit account, cash from the
     payment; via `postBalancedJournal` with idempotency key
     `payment-alloc:{paymentId}:{allocIndex}` — a poster **decision**, per Phase 3 of
     the parent program), realised FX via `journalGenerator.computeRealisedFx` when the
     doc carries a foreign booking rate (IAS 21 §28 — same engine as the JE path),
     `applySettlement` on the doc, `partyBalanceService.adjust*` in base. All in the
     same session.
   - `transaction.recordPartialPayment` itself gains the same authority branch at the
     top (its direct HTTP route must not stay broken for projections).
3. Payment **reversal** (`reverseTransaction` step 7a) branches through
   `restoreSettlement` — reversing a settlement whose parent is a projection restores
   the **document** (and party balance) instead of silently finding no JE balance.
4. `markPaid` (both invoice and bill) is re-implemented as **"record a full payment
   through payment.service"** (auto-allocation of the full remaining balance):
   - kills I-4 (transaction-first markPaid now settles the JE, party, GL — one engine,
     no special path, per CLAUDE.md);
   - kills I-5 (a real Payment document now exists for every markPaid; cash account is
     an optional parameter, defaulting via `accountResolver` — no more `$in` guess).
   - The existing `invoice-markpaid:{id}` idempotency key moves onto the new path so a
     historical markPaid can never double-post.
5. Void / write-off / credit paths: re-run their suites against document-authority
   fixtures; `adjustOpenItem` upgrade (§3.4) lands here with its callers' hand-writes
   removed in the same commit (one writer per number, atomically swapped).

**Live tests (the proof, all on the real-DB tier):** approve invoice-first invoice →
partial payment → rest → aging/drift/assurance green after each step; foreign-currency
invoice-first settlement books realised FX; credit note then payment cannot over-collect
(optimistic guard); payment reversal restores the doc; void after partial payment;
markPaid on BOTH conventions → Payment doc exists, drift 0; INV-202607-24894 settleable
end-to-end on a copy of live data.

### Phase 3 — Recognition hardening *(fail-closed + resolver harmonization)*

1. **I-3:** `postArJournal` tax leg — when `taxAmount > 0`, resolve the output-tax
   account via `taxEngine`/`accountResolver` by **code** and **REFUSE** the whole
   recognition if unresolvable (plain language: "set up your tax accounts, then approve
   again"). Audit + mirror the bill-side input-tax leg. A tax-bearing document may never
   half-post.
2. **I-9:** migrate the four remaining regex/`$in` resolution sites onto
   `accountResolver` (write-off 6370/1110, debit-note 1110/4110, settlement cash
   default, tax legs). Behavior change is strictly: heal-or-refuse instead of
   throw-or-skip.
3. **I-6:** move `_mirrorInvoiceOrBill` **inside** the `createTransaction`
   `withTransaction` — a credit sale whose document cannot be written does not post
   (correctness > convenience). Safety net: invariant-5-style assurance sub-check
   "every credit-sale/purchase JE has its mirror document" so any legacy gap is visible.

### Phase 4 — History integrity *(I-7, I-8)*

1. **I-7:** add `transactionDate` to `checkImmutability.restrictedFields` for posted
   entries. Moving a posted entry between periods = reverse + repost, like every other
   financial mutation. Sweep callers first (editTransaction's non-financial edit path is
   the only suspect); add the audit-doc note.
2. **I-8:** new append-only `Settlement` collection (businessId, parentJeId, docRef,
   paymentId, childJeId, baseAmount, docAmount, fxDelta, createdAt) written in the same
   session as each settlement; readers that today scan `settlements[]`
   (reversal-restore lookup, projectionRebuild, installment progress) migrate to it;
   `settlements[]` is **frozen** (no new appends after cutover, existing data kept —
   history is never deleted) with a backfill migration copying old subdocs into the
   collection first, verified by count+sum parity before the cutover flag flips.
   This is its own phase because it touches reversal — the riskiest reader — and must
   not share a blast radius with Phase 2.

### Phase 5 — Repair, standing proof, docs

1. Optional `scripts/recognizeUnpostedDocuments.js` — dry-run default, driven by the
   **same query as invariant 5**, re-triggers `_recognizeApprovedInvoice/Bill` per doc
   (idempotent: `invoice-ar:{id}` keys make re-runs safe). Run on live only if the user
   asks (they ruled the Rs 88,500 pair test data).
2. Re-verify live: drift 0 on all businesses, booksAssurance green, the two test
   invoices either recognized or still flagged by invariant 5 (their choice).
3. Update `ar-ap-domain-refactor.md` (mark the settlement milestone done, record the
   authority-per-item decision and the full-M9 deferral) and the audit docs' P3 table.

---

## 5. Zero-regression guarantees (how "no new issues" is engineered, not hoped)

1. **Transaction-first is the null case.** Journal-authority branches are the existing
   code paths, moved behind the resolver, not rewritten. Golden parity tests pin old
   output ≡ new output for pure-transaction-first fixtures at every converged reader.
2. **Additive API.** Every response gains rows (invoice-first items) but no field
   changes name, type, or meaning. The frontend needs zero changes for correctness
   (it already sends `parentTransactionId` or `documentType+documentId`, both of which
   the resolver accepts).
3. **The poster is untouched.** Balanced-entry enforcement, running balances,
   idempotency, tenant guard — the chokepoint that already works stays frozen.
4. **Immutability preserved.** Projection JEs are never financially mutated;
   document-side settlement writes only document fields. `checkImmutability` gets
   *stricter* (I-7), never looser.
5. **Every phase gate:** full Jest (301+ suites) + `tests/live` + live `ledgerDrift` = 0
   + booksAssurance green, before the next phase starts. Any red = stop.
6. **No destructive migration.** Nothing is deleted or rewritten in place; the only
   data-touching steps are additive (Settlement backfill) or opt-in (recognizer script),
   both dry-run-first with count/sum parity checks.
7. **Concurrency:** every new balance write uses the F5 optimistic-guard pattern with a
   409 on a lost race; live tests include a concurrent double-settle race.
8. **Fail-closed bias.** Every new branch that cannot resolve its authority refuses
   loudly in plain language. No branch may skip-and-log a financial consequence.

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Unit confusion (base vs document currency) — the F2 bug class | §2.4 discipline; every signature names its unit; FX live tests on both authorities |
| Double-count in the union (an item on both sides) | Impossible by construction (`isProjection` filter + rem-null on projections) **and** asserted: a live invariant test posts both conventions and checks the union count |
| Credit-note double-adjust during §3.4 swap | Caller hand-writes removed in the same commit as the adjuster upgrade; suite asserts net effect unchanged |
| Ali Raza numbers don't tie in Phase 1.4 | Hard stop; diagnose before any write-path change ships |
| Settlement-collection cutover breaks reversal restore | Own phase; backfill parity check; reversal live test runs against both storage layouts during transition |
| markPaid unification changes an API contract someone relies on | Response shape kept; only side effects become *more* complete (Payment doc now exists) |

## 7. Out of scope (explicitly deferred, not forgotten)

- Full M9 retirement (documents authoritative for *all* AR/AP, synthetic docs for
  installments/manual JEs) — direction unchanged, separate program.
- T2 performance items, DB password rotation (operational, not accounting).
- New features (payment terms engine, dunning automation, sales orders) — this spec is
  correctness-only.

## 8. As-built deviations (recorded during implementation, same day)

1. **§3.4 (adjustOpenItem callers) — kept, not re-plumbed.** The credit callers
   already adjust the document in exact document units inside the same
   transaction; making the adjuster also write the document would double-reduce
   it, and converting base→doc inside the adjuster reintroduces rounding
   round-trips. The adjuster's projection no-op is now *documented as the
   design*; the new settlement writes (the actual new risk) are guarded.
2. **Phase 3.3 assurance net ("every credit-sale JE has a mirror document") —
   dropped.** JE-only open items (installments, manual journals without an
   invoice number) are legitimate, so the check would false-alarm forever. The
   transactional mirror (I-6) IS the guarantee for everything that mirrors.
3. **Phase 4.2 (Settlement collection, I-8) — deferred, with the reader
   inventory established:** `settlements[]` is load-bearing for the
   TransactionDetail UI, `GET /transactions/:id/settlements`, the M9
   projection rebuild, reversal cleanup, and two installment writers. It is a
   scalability debt, not a correctness break (balances are authoritative in
   aggregate fields). Migrating load-bearing payment-history storage inside
   the same change-set as the settlement-engine rework would trade a
   correctness guarantee for a capacity nicety — exactly backwards. Follow-up
   design: append-only Settlement collection, dual-source reads with
   `settlements[]` fallback, backfill with count+sum parity, then freeze.
4. **Found and fixed beyond the register:** `POST /:id/transition` allowed raw
   flips to paid/cancelled/voided/written_off (no settlement, no reversal) —
   now routed through the proper flows; and Phase 0's resurrected
   `idx_je_invoice_number` UNIQUE index made every multi-leg recognition
   (tax-bearing invoice-first approval, post-recognition write-off) an E11000
   — replaced by a non-unique lookup index; document-number uniqueness stays
   on the document collections, which the transactional mirror now extends to
   the ledger path atomically.

## 9. Effort map

| Phase | Size | Riskiest file |
|---|---|---|
| 1 | M | `ledgerIntegrity.service.js` |
| 2 | L | `payment.service.js` / `transaction.service.js` reversal |
| 3 | S–M | `invoice.service.js` / `bill.service.js` recognition |
| 4 | M | `JournalEntry.model.js` hooks + reversal readers |
| 5 | S | scripts + docs |
