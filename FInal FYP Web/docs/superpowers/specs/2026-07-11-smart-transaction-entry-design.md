# Smart Unified Transaction Entry — Design Spec

**Date:** 2026-07-11
**Status:** Approved (user delegated final call after design walkthrough)
**Repos:** `vousfin-backend-main` + `vousfin-frontend-main`

## Problem

The same real-world event produces different books depending on phrasing:

1. **The NL parser never extracts items, quantities, or unit prices.** "Bought 10 bags of rice for 5000" loses "rice", "10", and "500 each" — only amount/date/accounts survive.
2. **Word choice decides the accounting.** Saying "inventory" routes to `inventory_purchase` (DR Inventory); saying "purchased" routes to `expense` (DR some expense). The parser never asks *why* the thing was bought.
3. **Even the Inventory Purchase path never updates stock.** `transaction.service.createTransaction` blocks 7/7a already sync stock — but only when `inventoryItemId + inventoryQty` are supplied. The NL path never supplies them, so the ledger's Inventory balance rises while the stock subledger shows nothing.
4. **The item picker is buried and helpless.** In the 2,100-line `TransactionFormModal`, the inventory selector sits near the bottom, appears only when items already exist, and cannot create an item. Users must visit the Inventory page first.
5. **The manual form is accountant-shaped.** 25+ transaction types, DR/CR dropdowns, tax, installments — hostile to a non-accountant owner.

The backend accounting engine downstream is already correct (atomic stock sync, weighted-average + FIFO costing, COGS auto-post, reversal restores stock). The entire problem is the front door: extraction, classification, item linkage, and form UX.

## Goals

- One real-world purchase/sale story → one accounting representation, regardless of phrasing.
- A non-accountant can record stock purchases/sales correctly without knowing the words "inventory", "debit", or "COGS".
- Chart-of-accounts choice is deterministic and type-safe — the AI suggests, deterministic code decides, guardrails fail closed.
- Zero new accounting paths: everything flows through `transaction.service.createTransaction`. Ledger drift stays 0.

## Decisions (locked with user)

| Decision | Choice |
|---|---|
| Scope | Full overhaul: parser brain + inventory link + manual form |
| When to ask "stock or expense?" | Smart: use context, ask only when signals conflict |
| Unknown item found in text | Ask first ("Add Rice to your inventory?"), then create at save |
| Manual form | Simple mode (plain-question chips) + Advanced toggle to existing form |

## Architecture

### 1. Parser extraction upgrade (`services/nlParser/`)

New fields in the AI extraction schema (`promptBuilder.js`, `aiExtractionService.js`, `normalizationService.js`):

```
lineItems: [{ name, quantity, unit, unitPrice }] | null
purchaseIntent: "resale" | "business_use" | "long_term_asset" | null
saleAffectsStock: boolean
```

- Existing **inventory item names are injected into the prompt** (same mechanism as live account names) so the model can align "rice" → "Rice (bag)". Cap at ~100 item names, active items only.
- **Deterministic post-extraction repair** in `normalizationService`: if `quantity × unitPrice` disagrees with `amount` beyond 1% tolerance, derive the missing number when exactly one is absent, otherwise keep `amount` authoritative and drop the per-unit claim (lower `lineItems` confidence). The AI never gets the final word on arithmetic.
- The parser's `parsedData` passes `lineItems`, `purchaseIntent`, `saleAffectsStock` through `nlParserPreview.helper.js` to the frontend.

### 2. Intent resolver — decide vs ask (new `services/nlParser/services/intentResolver.js`)

Pure, deterministic, DB-free function. Inputs: normalized parse + business context (`inventoryItems`, `hasEverTrackedStock`). Output: `{ classification, question | null, matchedItem | null }`.

Decision table (checked in order):

| # | Condition | Result |
|---|---|---|
| 1 | lineItem name fuzzy-matches an existing inventory item | `resale`, prefill item — **no question** |
| 2 | Explicit resale cues ("for sale", "stock", "inventory", "to sell", "maal") | `resale` |
| 3 | `purchaseIntent = long_term_asset` OR item name hits the asset synonym table (furniture, vehicle, machine, computer…) | `long_term_asset` |
| 4 | Business has zero inventory items AND no resale cues | `business_use` — **no question** |
| 5 | Business tracks stock (≥1 inventory item) AND `lineItems` non-empty (physical goods parsed) AND no item match AND AI unsure (`purchaseIntent` null or low confidence) | **ask** the classification question |
| 6 | Otherwise | trust `purchaseIntent`, mark for review if confidence < threshold |

Classification question (rides the existing stateless clarification loop in `clarificationBuilder.js`):

> **"Will you sell this again, or use it in the business?"**
> Options: `Sell it again (it's stock)` / `Use it in the business` / `It's equipment we'll keep`

Item-matching reuses `matchAccountByName`'s 3-tier strategy generalized into a shared `matchByName(candidates, name)` util (exact → substring → word-overlap) so item and account matching behave identically.

### 3. Clarification loop extensions (`clarificationBuilder.js`)

Question priority order (one per round, existing round-cap raised from 2 → 3):

1. Amount missing (existing)
2. Payment source missing (existing)
3. **Stock-or-expense** (new, per intent resolver row 5)
4. **New-item consent**: "«Rice» isn't in your inventory yet. Add it as a new item?" — options `Yes, add it` / `No — record without stock tracking`
5. **Quantity**: asked only when user consented to item creation/linkage and no quantity was parsed: "How many did you buy, and what unit? (e.g. 10 bags)"
6. Vendor name when credit purchase has no counterparty (existing AP rule requires vendor)
7. Account-purpose fallback (existing)

All stateless: answers are appended to the re-parse text exactly as today.

### 4. Intelligent Chart of Accounts (backend)

**Resolution chain** — extract the deterministic chain from `utils/importAccountResolver.js` into a shared resolver used by the NL confirm path:

1. `matchAccountByName` (exact → substring → word overlap)
2. `matchByCode` ("1150", "1150 - Inventory")
3. `matchBySynonym` (bookkeeper vernacular → standard code)
4. Resolve-or-create **only from the DEFAULT_ACCOUNTS catalog** (`inferAccountShape` + additive creation, same guarantee as `syncMissingDefaults` — never invents non-catalog accounts)

**Intent → account guarantee:**

| Classification | Debit | Credit |
|---|---|---|
| `resale` | Inventory (1150) | Cash/Bank per paymentMethod; AP (2110) + vendor if "on credit" |
| `business_use` | Best-fit expense via subcategory→account map; fallback General/Misc Expenses — never a wrong-type account | same as above |
| `long_term_asset` | Fixed-asset account via synonym table (1210 furniture, 1220 equipment, 1230 vehicle, 1240 computers, 1258 machinery…) | same as above; financed → existing installment path |
| sale of stock | Cash/Bank/AR | Sales revenue; COGS pair auto-appended by existing block 7 |

**Type guardrails — fail closed** (new validation in the NL confirm/auto-post path + `validationService`):

- Purchase journals must debit Asset or Expense and credit Asset (cash/bank) or Liability.
- Sale journals must credit Income and debit Asset.
- Guardrail violation, unresolved account, or pending item creation → `requiresReview = true`, **auto-post hard-blocked**. The user always sees the form.
- Posting stays exclusively through `transaction.service.createTransaction` (canonical journalLines, idempotency, audit). No raw `JournalEntry.create`.

### 5. Confirm path carries the inventory link

The NL preview response gains:

```
inventory: {
  mode: "existing" | "create" | "none",
  itemId,                          // when existing
  newItem: { name, unit, unitCostPrice, quantity },  // when create (user consented)
  quantity
}
```

On save, the frontend sends `inventoryItemId + inventoryQty` (existing) **or** `newInventoryItem {name, unit, quantity, unitCostPrice}` (new). `createTransaction` handles `newInventoryItem` by creating the item via `inventoryService.createItem` **inside the same withTransaction session**, then reusing the existing 7a stock-sync block. Duplicate-name guard: re-run item matching server-side at save; if a same-name item exists, link instead of create (idempotent under retry).

### 6. Frontend — NL flow (`TransactionFormModal.jsx`)

- Clarification UI unchanged (already renders option buttons).
- `nlResultToFormValues` maps the `inventory` block → prefills `selectedInventoryItemId` + `inventoryQty`, or sets pending-new-item state.
- **Inventory section moves up** next to amount whenever the parse or type involves goods; shows a "New item: Rice — 10 bags @ 500 each" card (editable name/unit/qty/cost) when creation is pending.
- **Plain-language summary sentence** above the DR/CR preview: "You bought 10 bags of Rice for PKR 5,000, paid in cash. Stock will go up by 10." Generated client-side from form state (no AI call), follows product plain-copy rule.
- Sales with matched items show: "Stock will go down by 5. You have 12 in stock." Insufficient stock → plain inline error before save.

### 7. Frontend — Simple mode + Advanced toggle

New `SimpleEntryForm` component inside the manual tab; toggle persisted per user (localStorage), Simple is default.

Chips (plain language, i18n-ready incl. Urdu):

- **I paid for something** → expense flow: What for? / Amount / How paid / Date (+ smart account suggestion via same resolver)
- **I got paid** → income flow: From whom? / Amount / How received / Date
- **I bought stock** → item picker with inline "+ new item" (name, qty, unit, cost auto-derived) / Amount / How paid
- **I sold stock** → item picker + qty (shows current stock) / Amount / How received
- **Money moved between accounts** → from/to account + amount
- **Something else** → switches to Advanced

Simple mode composes the **same react-hook-form state** and submits through the same save handler — no second save path. Advanced toggle reveals the existing full form with state intact.

### 8. Integrity & error handling

- Preview endpoints stay side-effect-free; all writes happen inside `createTransaction`'s atomic session (item create + stock + journal + balances all-or-nothing).
- Existing top-level `idempotencyKey` covers double-submit; server-side link-instead-of-create makes item creation idempotent.
- Auto-post gate: blocked when `inventory.mode = "create"`, when any account resolved below confidence threshold, or on guardrail violation.
- Tax engine, FX, installments, reversal logic untouched. Reversals already restore stock (verified in `createTransaction` reversal path).
- After implementation: `scripts/ledgerDrift.js` must read 0 on the seeded demo business.

### 9. Testing (TDD, per repo standard)

**Backend unit:** intent-resolver decision table (every row + conflict cases); lineItems arithmetic repair; clarification sequencing/round-cap; shared name-matcher parity; CoA chain incl. resolve-or-create-from-catalog and type guardrails (wrong-type account → review, never post).
**Backend integration:** NL parse → clarify → confirm → journal balanced + stock incremented + drift 0; new-item creation atomicity (forced failure leaves no item/stock/journal); duplicate-name retry links instead of creates; sale decrements stock + COGS lines; insufficient stock rejects pre-save; auto-post blocked on pending item.
**Frontend (Vitest):** chip → form-state mapping for all six chips; new-item card render/edit; plain-language summary strings; mode toggle persistence.

## Out of scope

- OCR/image parsing path (follow-up; shares `_finishParse` so it inherits most gains).
- Multi-line-item purchases posting per-item journals (v1 records the first/primary line item for stock; multi-item entry stays on the Invoice/Bill flows where it belongs).
- FIFO/valuation changes — costing engine untouched.
- Urdu translations beyond existing i18n scaffold keys.
