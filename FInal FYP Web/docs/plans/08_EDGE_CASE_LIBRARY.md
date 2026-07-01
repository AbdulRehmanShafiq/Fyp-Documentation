# 08 — Edge Case Library

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 1.0.0 |
| **Owner of** | Enumerated edge cases + their required behaviour |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> The permanent registry of adversarial and boundary scenarios the system MUST handle correctly. Each case has an ID, a trigger, and a **required behaviour**. The dataset generator ([05](./05_DATASET_GENERATOR_SPECIFICATION.md)) seeds these; the self-improvement loop ([07](./07_SELF_IMPROVEMENT_ENGINE.md)) proves them; the test suite ([10](./10_TESTING_STRATEGY.md)) locks them.

---

## 1. Purpose & scope

Prevent regressions by enumerating what "correct" means at the boundaries. "Required behaviour" is one of: **REJECT** (4xx, nothing persists), **BLOCK** (queue/hold, surfaced to user), **ADJUST** (post a compensating entry), **ALLOW+FLAG** (post, mark for review), **ALLOW** (valid). Every case maps to a test.

## 2. How to read a case

`EC-<AREA>-<n>` · Trigger → Required behaviour → Enforcement site. Areas: LEDGER, PERIOD, AR, AP, PAY, INV, PROC, TAX, FX, PAYROLL, ASSET, LOAN, AI, IMPORT, CONCURRENCY, AUTH, CONTROL, DATA.

## 3. Ledger & journal

| ID | Trigger | Required behaviour | Enforced by |
|---|---|---|---|
| EC-LEDGER-01 | Debit total ≠ credit total | REJECT | balance check |
| EC-LEDGER-02 | Same account as debit and credit (2-line) | REJECT | schema validator |
| EC-LEDGER-03 | Amount 0 / negative / NaN / Infinity | REJECT | input hardening |
| EC-LEDGER-04 | Amount > 1e12 | REJECT (overflow) | input hardening |
| EC-LEDGER-05 | Amount with >2 dp | ADJUST (round to cents) or REJECT per policy | input hardening |
| EC-LEDGER-06 | Compound entry with 1 line | REJECT (≥2 required) | poster validation |
| EC-LEDGER-07 | Edit amount of a POSTED entry | REJECT | immutability hook |
| EC-LEDGER-08 | Delete a posted entry | REJECT (reverse instead) | no hard delete |
| EC-LEDGER-09 | Reverse an already-reversed entry | REJECT | reversal guard |
| EC-LEDGER-10 | Reverse an entry with partial payments | REJECT | reversal guard |
| EC-LEDGER-11 | Retried identical request (idempotency key) | ALLOW (returns existing) | idempotency |
| EC-LEDGER-12 | Journal line account from another tenant | REJECT | tenant validation |

## 4. Periods & close

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-PERIOD-01 | Post into a LOCKED period | REJECT (423) |
| EC-PERIOD-02 | Non-system post into a CLOSED period | REJECT |
| EC-PERIOD-03 | System closing/opening entry into CLOSED | ALLOW |
| EC-PERIOD-04 | Reversal whose reversal-date lands in a LOCKED period | REJECT |
| EC-PERIOD-05 | Transaction dated with no covering period | ALLOW (no lock) but flag for period setup |
| EC-PERIOD-06 | Close a period with unbalanced trial balance | REJECT close |
| EC-PERIOD-07 | Double year-end close | REJECT (idempotent close) |
| EC-PERIOD-08 | Future-dated transaction | ALLOW+FLAG (valid but reviewable) |
| EC-PERIOD-09 | Back-dated into an OPEN prior period | ALLOW |

## 5. Accounts receivable

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-AR-01 | Credit sale over customer credit limit (action=block) | BLOCK |
| EC-AR-02 | Credit sale over limit (action=warn) | ALLOW+FLAG |
| EC-AR-03 | Credit note exceeding invoice balance | REJECT (over-credit) |
| EC-AR-04 | Applying credit note to a paid invoice | REJECT |
| EC-AR-05 | Duplicate invoice number | REJECT (unique index) |
| EC-AR-06 | Invoice due date before issue date | REJECT (validator) |
| EC-AR-07 | Void a partially-paid invoice | ADJUST (reverse GL, keep history) |
| EC-AR-08 | Dunning escalation past level 5 | CLAMP at 5 |
| EC-AR-09 | Write off then receive payment | ADJUST (reverse write-off) |

## 6. Accounts payable & procurement

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-AP-01 | Vendor credit applied beyond remaining amount | REJECT (over-apply) |
| EC-AP-02 | Vendor credit driving AP negative | REJECT |
| EC-PROC-01 | Bill quantity > received quantity (over-billed) | BLOCK (3-way match) |
| EC-PROC-02 | Bill against un-received GRN | BLOCK |
| EC-PROC-03 | GRN confirm re-run (double receipt) | ALLOW once (`inventoryApplied` guard) |
| EC-PROC-04 | Price variance beyond ±5% tolerance | BLOCK / discrepancy |
| EC-PROC-05 | Duplicate vendor invoice (same ref) | BLOCK (duplicate check) |
| EC-PROC-06 | Partial delivery | ALLOW (partial GRN, PO stays partially_received) |
| EC-PROC-07 | GRN with rejected quantity | ALLOW (record rejection, accrue only accepted) |

## 7. Payments

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-PAY-01 | Payment exceeding invoice balance | ALLOW (excess → advance/`unappliedAmount`) |
| EC-PAY-02 | Duplicate payment (same allocation twice) | REJECT (over-settle guard) |
| EC-PAY-03 | Underpayment | ALLOW (partial; `partiallyPaidAmount`) |
| EC-PAY-04 | Allocate one payment across multiple invoices | ALLOW (Σ allocations ≤ amount) |
| EC-PAY-05 | Void a payment | ADJUST (reverse settlement JE) |
| EC-PAY-06 | Payment to a deleted/archived party | REJECT or ALLOW-unlinked per rule |
| EC-PAY-07 | Payment in foreign currency vs base AR/AP | ADJUST (realized FX gain/loss) |

## 8. Inventory

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-INV-01 | Sell more than on-hand stock | REJECT (negative stock forbidden) |
| EC-INV-02 | FIFO consume across multiple layers | ALLOW (correct layered COGS) |
| EC-INV-03 | Purchase updates weighted-average cost | ALLOW (recompute avg) |
| EC-INV-04 | Zero-cost item sale | ALLOW+FLAG (COGS 0, reviewable) |
| EC-INV-05 | Inventory adjustment / write-off | ADJUST (DR 6495 / CR 1150) |
| EC-INV-06 | Stock value diverges from GL 1150 | DETECT (VE-7) → repair |
| EC-INV-07 | Duplicate SKU / barcode | REJECT (unique index) |

## 9. Tax

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-TAX-01 | Client-supplied tax > engine value by >1% | ADJUST (clamp to engine, R-03) |
| EC-TAX-02 | Tax on a non-taxable type (transfer/FX/depreciation) | ALLOW (no tax applied) |
| EC-TAX-03 | Reverse charge on imported service | ALLOW (self-supply legs) |
| EC-TAX-04 | WHT on non-filer vendor | ALLOW (higher rate) |
| EC-TAX-05 | Tax enabled but tax accounts missing | ADJUST (`ensureTaxAccounts` seeds) |
| EC-TAX-06 | Inclusive vs exclusive mismatch | ALLOW (mode-correct math) |
| EC-TAX-07 | Multi-component tax (CGST+SGST) | ALLOW (per-component legs) |

## 10. Foreign currency

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-FX-01 | Settlement rate ≠ booking rate | ADJUST (realized gain/loss) |
| EC-FX-02 | Missing rate for date | ALLOW (caller rate / 1:1) + FLAG |
| EC-FX-03 | Attempt to overwrite historical rate | REJECT (immutable) |
| EC-FX-04 | Month-end open foreign AR/AP | ADJUST (unrealized revaluation, reversed next period) |

## 11. Payroll, assets, loans

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-PAYROLL-01 | Second live run for same period | REJECT (one live run) |
| EC-PAYROLL-02 | Reverse a posted run | ALLOW (reversal entries) |
| EC-PAYROLL-03 | Salary structure with no version in force | REJECT (need effective version) |
| EC-ASSET-01 | Depreciate same year twice | REJECT (`depreciationPostedYears` guard); scheduled job idempotent per-year |
| EC-ASSET-04 | Scheduled depreciation runs before a full year elapsed | SKIP (`isDepreciationDue` gate) |
| EC-ASSET-02 | Depreciate beyond salvage value | CLAMP at salvage |
| EC-ASSET-03 | Dispose with proceeds ≠ book value | ADJUST (gain/loss) |
| EC-LOAN-01 | Overpay an installment | ADJUST (waterfall interest→principal→next) |
| EC-LOAN-02 | Early settlement | ALLOW (mark remaining paid, discount) |
| EC-LOAN-03 | Restructure mid-plan | ALLOW (rebuild unpaid rows, keep paid history) |

## 12. AI / NLP / import

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-AI-01 | AI suggests an account not in CoA | REJECT posting; resolve/flag (never invent) |
| EC-AI-02 | Confidence ≥98% + exact match + opt-in | ALLOW (auto-post) |
| EC-AI-03 | Confidence ≥98% but fuzzy match | BLOCK auto-post → preview |
| EC-AI-04 | Confidence 95–98% | ALLOW+FLAG (prefill, require confirm) |
| EC-AI-05 | Confidence <95% | BLOCK → clarifying question |
| EC-AI-06 | Auto-post of large amount over approval threshold | BLOCK (park for approval) |
| EC-IMPORT-01 | Excel row Low confidence | BLOCK (hold in failed[], exportable) |
| EC-IMPORT-02 | Excel row Medium confidence | ALLOW+FLAG (`needsSpotCheck`) |
| EC-IMPORT-03 | Excel account name unresolvable | BLOCK (failed[] with reason) |
| EC-IMPORT-04 | Re-import same file | ALLOW (idempotency prevents dupes) |

## 13. Concurrency, auth, control, data

| ID | Trigger | Required behaviour |
|---|---|---|
| EC-CONCURRENCY-01 | Two writes to same account balance | ALLOW (transaction retry + recovery pass) |
| EC-CONCURRENCY-02 | Double-click submit (<10s) | REJECT (double-submit guard, UI form) |
| EC-CONCURRENCY-03 | Concurrent number sequence | ALLOW (atomic counter, no dup) |
| EC-AUTH-01 | Action without permission | REJECT (403, RBAC) |
| EC-AUTH-02 | Self-approval when disallowed | REJECT (SoD) |
| EC-AUTH-03 | Expired/blacklisted JWT | REJECT (401) |
| EC-CONTROL-01 | Direct post to control account (AR/AP/tax) via normal type | ALLOW — control flag is metadata, not a block (see Doc 01 §4.4) |
| EC-DATA-01 | Missing required party name | ALLOW (auto-create) or REJECT per path |
| EC-DATA-02 | Invalid currency code | REJECT |
| EC-DATA-03 | Operator-injection in query payload | REJECT (mongo-sanitize) |
| EC-DATA-04 | Cross-tenant id in request | REJECT (tenant scoping) |

## 14. Business rules

| ID | Rule |
|---|---|
| EL-01 | Every edge case has an ID, trigger, required behaviour, and a test. |
| EL-02 | New production incidents become new EC entries permanently. |
| EL-03 | "Required behaviour" values are limited to the five defined actions. |
| EL-04 | Removing an EC requires a documented rationale in CHANGELOG. |

## 15. Acceptance criteria

- [ ] Each EC above maps to at least one automated test.
- [ ] The generator seeds every EC at non-zero density.
- [ ] The suite fails if any EC's required behaviour regresses.

## 16. Failure modes / 17. Regression

The library *is* the regression contract for boundaries. A change that alters an EC's behaviour must update the EC, its test, and CHANGELOG together.

## 18. Implementation guidance

When implementing a feature, grep this document for its area, implement to the required behaviour, and add tests referencing the EC IDs. When you find a new boundary, add it here first.

## 19. Cross references

[04](./04_TRANSACTION_LIFECYCLE.md) · [06_VALIDATION_ENGINE.md](./06_VALIDATION_ENGINE.md) · [10_TESTING_STRATEGY.md](./10_TESTING_STRATEGY.md) · [12_SECURITY_AND_AUDIT.md](./12_SECURITY_AND_AUDIT.md)

## 20. Revision history

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-07-01 | Initial catalog (~90 cases across 17 areas), grounded in shipped guards. |

## 21. Progress checklist

- [x] Cases enumerated per area with required behaviour
- [x] Control-account non-block decision recorded (EC-CONTROL-01)
- [ ] Every EC linked to a concrete test ID
- [ ] Generator density per EC configured
