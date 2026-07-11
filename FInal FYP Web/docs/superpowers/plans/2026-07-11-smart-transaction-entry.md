# Smart Unified Transaction Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One real-world purchase/sale story → one accounting representation regardless of phrasing: the NL parser extracts items/quantities, classifies *why* something was bought (resale / business use / asset), asks one plain question only when torn, links or creates inventory items at save time, and the manual form gains a plain-language Simple mode — all through the existing `createTransaction` pipeline.

**Architecture:** Extend the existing stateless NL parse→clarify→confirm loop (backend `services/nlParser/`, frontend `TransactionFormModal.jsx`). A new pure `intentResolver` applies a deterministic decision table over parsed line items + business context. Chart-of-accounts choice reuses the deterministic `resolveForImport` chain (name→code→synonym→create-from-catalog). New-item creation happens inside `createTransaction`'s atomic persist session. No new accounting paths.

**Tech Stack:** Node/Express/Mongoose + Jest (backend), React 19/Vite/react-hook-form/Vitest (frontend). AI provider: DeepSeek via `services/deepseek.service.js` (JSON mode).

**Spec:** `docs/superpowers/specs/2026-07-11-smart-transaction-entry-design.md`

## Global Constraints

- Working dirs: backend tasks run from `vousfin-backend-main/`, frontend tasks from `vousfin-frontend-main/`. All file paths below are relative to the repo the task names.
- **Never** create a `JournalEntry` outside `transaction.service.createTransaction` / the ledger posters. Preview endpoints must stay side-effect-free.
- Every journal entry must balance (Σ debit = Σ credit). After backend tasks, `node scripts/ledgerDrift.js` must report drift 0.
- Plain language in all user-facing copy — no accounting jargon as primary text (product rule).
- Auto-post is hard-blocked when a new inventory item is pending or a guardrail flags the journal shape.
- Backend tests: `npx jest <file> --silent` from `vousfin-backend-main/`. Frontend tests: `npx vitest run <file>` from `vousfin-frontend-main/` (for FULL-suite background runs use `npx vitest run --reporter=json --outputFile=vitest-results.json` — the default reporter hangs when backgrounded).
- Clarification answer strings are load-bearing: `clarificationAnswers.js` literals must match what the frontend sends back verbatim. Never edit one side alone.
- TDD: every task writes its failing test first. Commit after every green step with the message given in the task.

---

### Task 1: Inventory item name matcher (backend)

**Files:**
- Create: `utils/itemMatcher.js`
- Test: `tests/unit/utils/itemMatcher.test.js`

**Interfaces:**
- Consumes: `matchAccountByName(accounts, name)` from `utils/accountMatcher.js` (existing; 3-tier exact→substring→word-overlap, returns `{ account, confidence, matchType }`).
- Produces: `matchItemByName(items, name)` → `{ item: object|null, confidence: number, matchType: 'exact'|'fuzzy'|'ambiguous'|'none' }`. `items` are **lean** docs shaped `{ _id, name, unit, unitCostPrice, currentStock }`.

- [ ] **Step 1: Write the failing test**

```js
// tests/unit/utils/itemMatcher.test.js
'use strict';
const { matchItemByName } = require('../../../utils/itemMatcher');

const ITEMS = [
  { _id: 'i1', name: 'Rice (bag)', unit: 'bags', unitCostPrice: 500, currentStock: 12 },
  { _id: 'i2', name: 'Sugar 1kg', unit: 'kg', unitCostPrice: 150, currentStock: 40 },
  { _id: 'i3', name: 'Basmati Rice Premium', unit: 'bags', unitCostPrice: 900, currentStock: 3 },
];

describe('matchItemByName', () => {
  test('exact match (case-insensitive) → confidence 1.0', () => {
    const r = matchItemByName(ITEMS, 'rice (bag)');
    expect(r.item._id).toBe('i1');
    expect(r.confidence).toBe(1.0);
    expect(r.matchType).toBe('exact');
  });

  test('word-overlap fuzzy match finds the tightest fit', () => {
    const r = matchItemByName(ITEMS, 'rice');
    expect(['i1', 'i3']).toContain(r.item._id);
    expect(r.confidence).toBeGreaterThan(0);
  });

  test('no match → null item, confidence 0', () => {
    const r = matchItemByName(ITEMS, 'diesel');
    expect(r.item).toBeNull();
    expect(r.confidence).toBe(0);
    expect(r.matchType).toBe('none');
  });

  test('empty inputs are safe', () => {
    expect(matchItemByName([], 'rice').item).toBeNull();
    expect(matchItemByName(ITEMS, '').item).toBeNull();
    expect(matchItemByName(null, 'rice').item).toBeNull();
  });

  test('returned item does not carry the temporary accountName field', () => {
    const r = matchItemByName(ITEMS, 'Sugar 1kg');
    expect(r.item.accountName).toBeUndefined();
    expect(r.item.name).toBe('Sugar 1kg');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest tests/unit/utils/itemMatcher.test.js --silent`
Expected: FAIL — `Cannot find module '../../../utils/itemMatcher'`

- [ ] **Step 3: Write minimal implementation**

```js
// utils/itemMatcher.js
//
// Inventory-item name matching for the NL parser — the SAME 3-tier algorithm
// (exact → substring → word overlap) as account matching, so "rice" resolves
// to "Rice (bag)" exactly the way "Rent" resolves to "Rent Expense".
// Items must be plain objects (lean docs) — mongoose documents would lose
// their prototype under the spread below.
'use strict';
const { matchAccountByName } = require('./accountMatcher');

const NONE = { item: null, confidence: 0, matchType: 'none' };

/**
 * @param {Array<{_id, name}>} items  the business's live inventory items (lean)
 * @param {string} name               free-text goods name from the parse
 * @returns {{ item: object|null, confidence: number, matchType: string }}
 */
function matchItemByName(items, name) {
  if (!Array.isArray(items) || items.length === 0 || !name) return { ...NONE };
  const shaped = items.map((i) => ({ ...i, accountName: i.name }));
  const res = matchAccountByName(shaped, name);
  if (!res.account) return { ...NONE };
  const { accountName, ...item } = res.account;
  return { item, confidence: res.confidence, matchType: res.matchType };
}

module.exports = { matchItemByName };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest tests/unit/utils/itemMatcher.test.js --silent`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/itemMatcher.js tests/unit/utils/itemMatcher.test.js
git commit -m "feat(nl): inventory item name matcher reusing the 3-tier account algorithm"
```

---

### Task 2: Journal shape guardrails (backend)

**Files:**
- Create: `utils/journalGuardrails.js`
- Test: `tests/unit/utils/journalGuardrails.test.js`

**Interfaces:**
- Produces: `checkJournalShape({ transactionType, debitAccountType, creditAccountType })` → `{ ok: boolean, violations: string[] }`. `transactionType` is the API Title-Case type (e.g. `'Inventory Purchase'`); account types are ChartOfAccount `accountType` values (`'Asset'|'Liability'|'Equity'|'Revenue'|'Expense'`). Missing inputs → `ok: true` (fail-open on *unknown*, fail-closed on *wrong* — an unresolved account is already blocked by the auto-post ID requirement).

- [ ] **Step 1: Write the failing test**

```js
// tests/unit/utils/journalGuardrails.test.js
'use strict';
const { checkJournalShape } = require('../../../utils/journalGuardrails');

describe('checkJournalShape', () => {
  test('valid purchase: DR Asset / CR Asset passes', () => {
    expect(checkJournalShape({
      transactionType: 'Inventory Purchase', debitAccountType: 'Asset', creditAccountType: 'Asset',
    })).toEqual({ ok: true, violations: [] });
  });

  test('purchase debiting Revenue is a violation', () => {
    const r = checkJournalShape({
      transactionType: 'Cash Purchase', debitAccountType: 'Revenue', creditAccountType: 'Asset',
    });
    expect(r.ok).toBe(false);
    expect(r.violations.length).toBe(1);
  });

  test('purchase crediting Revenue is a violation', () => {
    const r = checkJournalShape({
      transactionType: 'Expense', debitAccountType: 'Expense', creditAccountType: 'Revenue',
    });
    expect(r.ok).toBe(false);
  });

  test('credit purchase crediting a Liability (AP) passes', () => {
    expect(checkJournalShape({
      transactionType: 'Credit Purchase', debitAccountType: 'Expense', creditAccountType: 'Liability',
    }).ok).toBe(true);
  });

  test('valid sale: DR Asset / CR Revenue passes', () => {
    expect(checkJournalShape({
      transactionType: 'Inventory Sale', debitAccountType: 'Asset', creditAccountType: 'Revenue',
    }).ok).toBe(true);
  });

  test('sale crediting an Expense account is a violation', () => {
    expect(checkJournalShape({
      transactionType: 'Cash Sale', debitAccountType: 'Asset', creditAccountType: 'Expense',
    }).ok).toBe(false);
  });

  test('unknown transaction types have no rule → ok', () => {
    expect(checkJournalShape({
      transactionType: 'Journal Entry', debitAccountType: 'Equity', creditAccountType: 'Equity',
    }).ok).toBe(true);
  });

  test('missing account types → ok (nothing to judge)', () => {
    expect(checkJournalShape({ transactionType: 'Expense', debitAccountType: null, creditAccountType: null }).ok).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest tests/unit/utils/journalGuardrails.test.js --silent`
Expected: FAIL — `Cannot find module '../../../utils/journalGuardrails'`

- [ ] **Step 3: Write minimal implementation**

```js
// utils/journalGuardrails.js
//
// Structural type-safety net for AI-suggested journals (fail-closed at the
// auto-post gate): a purchase can never debit Revenue, a sale can never credit
// an Expense — no matter how confident the model was. Violation messages are
// plain language because they surface in the review banner.
'use strict';

const PURCHASE_LIKE = new Set([
  'Expense', 'Cash Purchase', 'Credit Purchase', 'Inventory Purchase',
  'Asset Purchase', 'Prepaid Expense',
]);
const SALE_LIKE = new Set(['Income', 'Cash Sale', 'Credit Sale', 'Inventory Sale']);

const DEBIT_OK_PURCHASE  = new Set(['Asset', 'Expense']);
const CREDIT_OK_PURCHASE = new Set(['Asset', 'Liability']);

/**
 * @param {{transactionType?:string, debitAccountType?:string, creditAccountType?:string}} p
 * @returns {{ ok: boolean, violations: string[] }}
 */
function checkJournalShape({ transactionType, debitAccountType, creditAccountType } = {}) {
  const violations = [];
  if (!transactionType || !debitAccountType || !creditAccountType) {
    return { ok: true, violations };
  }
  if (PURCHASE_LIKE.has(transactionType)) {
    if (!DEBIT_OK_PURCHASE.has(debitAccountType)) {
      violations.push(`This looks like a purchase, but the money is going into a ${debitAccountType} account — it should go to what you bought (an asset, stock, or an expense).`);
    }
    if (!CREDIT_OK_PURCHASE.has(creditAccountType)) {
      violations.push(`This looks like a purchase, but it is being paid from a ${creditAccountType} account — it should come from cash, bank, or an amount you owe.`);
    }
  } else if (SALE_LIKE.has(transactionType)) {
    if (debitAccountType !== 'Asset') {
      violations.push(`This looks like a sale, but the money received is landing in a ${debitAccountType} account — it should land in cash, bank, or receivables.`);
    }
    if (creditAccountType !== 'Revenue') {
      violations.push(`This looks like a sale, but it is being recorded against a ${creditAccountType} account instead of an income account.`);
    }
  }
  return { ok: violations.length === 0, violations };
}

module.exports = { checkJournalShape, PURCHASE_LIKE, SALE_LIKE };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest tests/unit/utils/journalGuardrails.test.js --silent`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/journalGuardrails.js tests/unit/utils/journalGuardrails.test.js
git commit -m "feat(nl): fail-closed journal shape guardrails for AI-suggested entries"
```

---

### Task 3: Clarification answer literals + detector (backend)

**Files:**
- Create: `services/nlParser/constants/clarificationAnswers.js`
- Test: `__tests__/nlParser.clarificationAnswers.test.js`

**Interfaces:**
- Produces: `ANSWER_OPTIONS` (frozen object of exact user-facing strings) and `detectAnswers(rawText)` → `{ intentAnswer: 'resale'|'business_use'|'long_term_asset'|null, itemConsent: true|false|null }`. The clarification loop appends answers verbatim to the re-parse text, so detection is substring-based on the canonical literals.

- [ ] **Step 1: Write the failing test**

```js
// __tests__/nlParser.clarificationAnswers.test.js
'use strict';
const { ANSWER_OPTIONS, detectAnswers } = require('../services/nlParser/constants/clarificationAnswers');

describe('detectAnswers', () => {
  test('detects each intent answer literal', () => {
    expect(detectAnswers(`bought rice\n\nAdditional details:\n- Will you sell this again? ${ANSWER_OPTIONS.RESALE}`).intentAnswer).toBe('resale');
    expect(detectAnswers(`x ${ANSWER_OPTIONS.BUSINESS_USE}`).intentAnswer).toBe('business_use');
    expect(detectAnswers(`x ${ANSWER_OPTIONS.ASSET}`).intentAnswer).toBe('long_term_asset');
  });

  test('detects item-consent answers', () => {
    expect(detectAnswers(`x ${ANSWER_OPTIONS.ADD_ITEM_YES}`).itemConsent).toBe(true);
    expect(detectAnswers(`x ${ANSWER_OPTIONS.ADD_ITEM_NO}`).itemConsent).toBe(false);
  });

  test('no answers present → nulls', () => {
    expect(detectAnswers('bought 10 bags of rice for 5000')).toEqual({ intentAnswer: null, itemConsent: null });
    expect(detectAnswers('')).toEqual({ intentAnswer: null, itemConsent: null });
  });

  test('detection is case-insensitive', () => {
    expect(detectAnswers('SELL IT AGAIN (IT\'S STOCK)').intentAnswer).toBe('resale');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest __tests__/nlParser.clarificationAnswers.test.js --silent`
Expected: FAIL — `Cannot find module`

- [ ] **Step 3: Write minimal implementation**

```js
// services/nlParser/constants/clarificationAnswers.js
//
// The clarification loop is stateless: option-button answers are appended to
// the re-parse text verbatim. These literals are therefore a CONTRACT between
// clarificationBuilder (which offers them), the frontend (which echoes them),
// and intentResolver (which detects them). Change them only together.
'use strict';

const ANSWER_OPTIONS = Object.freeze({
  RESALE:       "Sell it again (it's stock)",
  BUSINESS_USE: 'Use it in the business',
  ASSET:        "It's equipment we'll keep",
  ADD_ITEM_YES: 'Yes, add it',
  ADD_ITEM_NO:  'No — record without stock tracking',
});

/**
 * @param {string} rawText  the full (re-)parse input including appended answers
 * @returns {{ intentAnswer: 'resale'|'business_use'|'long_term_asset'|null, itemConsent: boolean|null }}
 */
function detectAnswers(rawText) {
  const t = String(rawText || '').toLowerCase();
  let intentAnswer = null;
  if (t.includes('sell it again')) intentAnswer = 'resale';
  else if (t.includes('use it in the business')) intentAnswer = 'business_use';
  else if (t.includes("equipment we'll keep") || t.includes('equipment we will keep')) intentAnswer = 'long_term_asset';

  let itemConsent = null;
  if (t.includes('yes, add it')) itemConsent = true;
  else if (t.includes('record without stock tracking')) itemConsent = false;

  return { intentAnswer, itemConsent };
}

module.exports = { ANSWER_OPTIONS, detectAnswers };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest __tests__/nlParser.clarificationAnswers.test.js --silent`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add services/nlParser/constants/clarificationAnswers.js __tests__/nlParser.clarificationAnswers.test.js
git commit -m "feat(nl): canonical clarification answer literals + deterministic detector"
```

---

### Task 4: Prompt + extraction plumbing for lineItems / purchaseIntent / inventory injection (backend)

**Files:**
- Modify: `services/nlParser/utils/promptBuilder.js` (buildSystemPrompt signature + new sections)
- Modify: `services/nlParser/services/aiExtractionService.js:31-37` (callAIExtraction signature)
- Modify: `services/nlParser/services/parserService.js:34-38` (pass opts.inventoryItems)
- Test: `__tests__/nlParser.promptLineItems.test.js`

**Interfaces:**
- Consumes: nothing new.
- Produces: `buildSystemPrompt(businessAccounts = [], inventoryItems = [])`; `callAIExtraction(rawInput, businessAccounts = [], inventoryItems = [])`; `parseTransaction(rawInput, businessAccounts, opts)` where `opts.inventoryItems` is an array of lean items `{ _id, name, unit, unitCostPrice, currentStock }`. The AI JSON schema gains `lineItems`, `purchaseIntent`, `saleAffectsStock`.

- [ ] **Step 1: Write the failing test**

```js
// __tests__/nlParser.promptLineItems.test.js
'use strict';
const { buildSystemPrompt } = require('../services/nlParser/utils/promptBuilder');

const ITEMS = [
  { _id: 'i1', name: 'Rice (bag)', unit: 'bags' },
  { _id: 'i2', name: 'Sugar 1kg', unit: 'kg' },
];

describe('buildSystemPrompt — smart entry fields', () => {
  test('JSON schema includes lineItems, purchaseIntent, saleAffectsStock', () => {
    const p = buildSystemPrompt([], []);
    expect(p).toContain('"lineItems"');
    expect(p).toContain('"purchaseIntent"');
    expect(p).toContain('"saleAffectsStock"');
  });

  test('inventory item names are injected when provided', () => {
    const p = buildSystemPrompt([], ITEMS);
    expect(p).toContain('INVENTORY ITEMS THIS BUSINESS TRACKS');
    expect(p).toContain('"Rice (bag)"');
    expect(p).toContain('"Sugar 1kg"');
  });

  test('no inventory section when the business tracks nothing', () => {
    const p = buildSystemPrompt([], []);
    expect(p).not.toContain('INVENTORY ITEMS THIS BUSINESS TRACKS');
  });

  test('additional-details override rule is present', () => {
    const p = buildSystemPrompt([], []);
    expect(p).toContain('Additional details');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest __tests__/nlParser.promptLineItems.test.js --silent`
Expected: FAIL — prompt lacks the new fields/sections.

- [ ] **Step 3: Implement**

In `services/nlParser/utils/promptBuilder.js`:

3a. Change the signature at line 28: `function buildSystemPrompt(businessAccounts = [], inventoryItems = [])`.

3b. After the existing `accountsSection` block (after line 61), add:

```js
  // ── Build live inventory items section (smart entry) ─────────────────────
  let inventorySection = '';
  if (Array.isArray(inventoryItems) && inventoryItems.length > 0) {
    const names = inventoryItems.slice(0, 100).map((i) => `"${i.name}"`).join(', ');
    inventorySection = `
INVENTORY ITEMS THIS BUSINESS TRACKS (when the goods in the input are the same thing, use the EXACT name from this list in lineItems[].name):
${names}
`;
  }
```

3c. Inject `${inventorySection}` into the template string immediately after `${accountsSection}` (line 132).

3d. Append these numbered rules after rule 27 in the CRITICAL RULES block:

```
28. Extract PHYSICAL GOODS as lineItems: [{"name","quantity","unit","unitPrice"}]. Example: "bought 10 bags of rice at 500 each" → lineItems = [{"name":"rice","quantity":10,"unit":"bags","unitPrice":500}]. Services, rent, fees, utilities are NOT lineItems — use [] for them.
29. For PURCHASES of goods set purchaseIntent: "resale" (bought to sell again — stock, inventory, maal, goods for the shop), "business_use" (consumed/used up by the business), "long_term_asset" (equipment, furniture, vehicle, machine kept long-term), or null when the input does not say.
30. For SALES of physical goods set saleAffectsStock = true; for service/consulting income set it false.
31. When the input contains an "Additional details:" section, those lines are the user's direct answers to follow-up questions — treat them as authoritative and let them override anything you inferred from the first sentence.
```

3e. Add the three fields to the JSON response schema (before `"confidence"`):

```
  "lineItems": [{"name": "string", "quantity": number_or_null, "unit": "string or null", "unitPrice": number_or_null}],
  "purchaseIntent": "resale or business_use or long_term_asset or null",
  "saleAffectsStock": true_or_false,
```

In `services/nlParser/services/aiExtractionService.js`, change `callAIExtraction`:

```js
async function callAIExtraction(rawInput, businessAccounts = [], inventoryItems = []) {
  const messages = [
    { role: 'system', content: buildSystemPrompt(businessAccounts, inventoryItems) },
    { role: 'user', content: buildUserPrompt(rawInput) },
  ];
  return generate(messages);
}
```

In `services/nlParser/services/parserService.js` line 36, pass items through:

```js
  const rawExtraction = await callAIExtraction(rawInput, businessAccounts, opts.inventoryItems || []);
```

- [ ] **Step 4: Run tests**

Run: `npx jest __tests__/nlParser.promptLineItems.test.js __tests__/nlParser.phase3.test.js __tests__/nlParser.tax-liability-inventory.test.js __tests__/nlParser.hardening-step6.test.js --silent`
Expected: ALL PASS (new + existing NL suites — signature changes are backward compatible).

- [ ] **Step 5: Commit**

```bash
git add services/nlParser/utils/promptBuilder.js services/nlParser/services/aiExtractionService.js services/nlParser/services/parserService.js __tests__/nlParser.promptLineItems.test.js
git commit -m "feat(nl): extraction schema learns lineItems + purchaseIntent + live inventory injection"
```

---

### Task 5: Normalization — lineItems arithmetic repair + purchaseIntent (backend)

**Files:**
- Modify: `services/nlParser/services/normalizationService.js` (new fields in `normalizeExtraction`, two new functions, extend module.exports)
- Test: `__tests__/nlParser.lineItemNormalization.test.js`

**Interfaces:**
- Produces: `normalized.lineItems` = `[{ name, quantity, unit, unitPrice }]` (never null, `[]` when none); `normalized.purchaseIntent` ∈ `'resale'|'business_use'|'long_term_asset'|null`; `normalized.saleAffectsStock` boolean. Exported for tests: `normalizeLineItems(raw, amount)`.
- Rule: for a single line item, `quantity × unitPrice` must agree with the headline amount within 1%; otherwise the missing part is derived from `amount` (amount is authoritative — the AI never wins an arithmetic dispute).

- [ ] **Step 1: Write the failing test**

```js
// __tests__/nlParser.lineItemNormalization.test.js
'use strict';
const { normalizeLineItems, normalizeExtraction } = require('../services/nlParser/services/normalizationService');

describe('normalizeLineItems', () => {
  test('clean extraction passes through', () => {
    const out = normalizeLineItems([{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }], 5000);
    expect(out).toEqual([{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }]);
  });

  test('AI arithmetic that disagrees with amount is repaired from amount', () => {
    // 10 × 600 = 6000 ≠ 5000 → unitPrice recomputed as amount / qty
    const out = normalizeLineItems([{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 600 }], 5000);
    expect(out[0].unitPrice).toBe(500);
  });

  test('missing unitPrice is derived from amount / quantity', () => {
    const out = normalizeLineItems([{ name: 'rice', quantity: 4, unit: 'bags', unitPrice: null }], 5000);
    expect(out[0].unitPrice).toBe(1250);
  });

  test('missing quantity is derived when amount / unitPrice is a near-integer', () => {
    const out = normalizeLineItems([{ name: 'rice', quantity: null, unit: 'bags', unitPrice: 500 }], 5000);
    expect(out[0].quantity).toBe(10);
  });

  test('nameless entries are dropped; non-arrays return []', () => {
    expect(normalizeLineItems([{ name: '', quantity: 1 }], 100)).toEqual([]);
    expect(normalizeLineItems(null, 100)).toEqual([]);
    expect(normalizeLineItems('junk', 100)).toEqual([]);
  });

  test('multi-item extractions are not arithmetic-repaired (v1)', () => {
    const raw = [
      { name: 'rice', quantity: 10, unit: 'bags', unitPrice: 300 },
      { name: 'sugar', quantity: 5, unit: 'kg', unitPrice: 150 },
    ];
    const out = normalizeLineItems(raw, 5000);
    expect(out[0].unitPrice).toBe(300); // untouched
  });
});

describe('normalizeExtraction — new fields', () => {
  test('purchaseIntent + saleAffectsStock + lineItems land on normalized', () => {
    const { normalized } = normalizeExtraction({
      intent: 'buy stock', transactionType: 'inventory_purchase', amount: 5000,
      lineItems: [{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }],
      purchaseIntent: 'resale', saleAffectsStock: false,
      confidence: { intent: 0.9, amount: 0.9, date: 0.9, accountMapping: 0.9 },
    });
    expect(normalized.lineItems).toHaveLength(1);
    expect(normalized.purchaseIntent).toBe('resale');
    expect(normalized.saleAffectsStock).toBe(false);
  });

  test('invalid purchaseIntent → null; absent lineItems → []', () => {
    const { normalized } = normalizeExtraction({
      intent: 'x', transactionType: 'expense', amount: 100,
      purchaseIntent: 'because-i-wanted-it',
      confidence: {},
    });
    expect(normalized.purchaseIntent).toBeNull();
    expect(normalized.lineItems).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest __tests__/nlParser.lineItemNormalization.test.js --silent`
Expected: FAIL — `normalizeLineItems is not a function`.

- [ ] **Step 3: Implement**

In `services/nlParser/services/normalizationService.js`:

3a. Inside `normalizeExtraction`, add to the `normalized` object (after the `netAmount` line, ~line 82):

```js
    // Smart entry — physical goods + why they were bought
    lineItems:             normalizeLineItems(rawExtraction.lineItems, normalizeAmount(rawExtraction.amount)),
    purchaseIntent:        normalizePurchaseIntent(rawExtraction.purchaseIntent),
    saleAffectsStock:      rawExtraction.saleAffectsStock === true || rawExtraction.saleAffectsStock === 'true',
```

3b. Add the two functions near the other normalizers:

```js
// Amount is authoritative: when a single parsed line item's qty × unitPrice
// disagrees with the headline amount by more than 1%, the per-unit claim is
// recomputed from amount. The AI never gets the final word on arithmetic.
const LINE_ITEM_TOLERANCE = 0.01;

function normalizeLineItems(raw, amount) {
  if (!Array.isArray(raw)) return [];
  const items = raw
    .map((li) => ({
      name:      normalizeString(li?.name),
      quantity:  normalizePositiveFloat(li?.quantity),
      unit:      normalizeString(li?.unit),
      unitPrice: normalizeAmount(li?.unitPrice),
    }))
    .filter((li) => li.name);

  if (items.length === 1 && Number.isFinite(amount) && amount > 0) {
    const li = items[0];
    if (li.quantity && li.unitPrice) {
      const implied = li.quantity * li.unitPrice;
      if (Math.abs(implied - amount) / amount > LINE_ITEM_TOLERANCE) {
        li.unitPrice = Math.round((amount / li.quantity) * 100) / 100;
      }
    } else if (li.quantity && !li.unitPrice) {
      li.unitPrice = Math.round((amount / li.quantity) * 100) / 100;
    } else if (!li.quantity && li.unitPrice && li.unitPrice <= amount) {
      const q = amount / li.unitPrice;
      if (Math.abs(q - Math.round(q)) < 0.02) li.quantity = Math.round(q);
    }
  }
  return items;
}

function normalizePurchaseIntent(raw) {
  const v = String(raw || '').toLowerCase().trim();
  return ['resale', 'business_use', 'long_term_asset'].includes(v) ? v : null;
}
```

3c. Extend `module.exports` with `normalizeLineItems`.

- [ ] **Step 4: Run tests**

Run: `npx jest __tests__/nlParser.lineItemNormalization.test.js __tests__/nlParser.phase3.test.js --silent`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add services/nlParser/services/normalizationService.js __tests__/nlParser.lineItemNormalization.test.js
git commit -m "feat(nl): normalize lineItems with deterministic arithmetic repair + purchaseIntent"
```

---

### Task 6: Intent resolver — the decision table (backend)

**Files:**
- Create: `services/nlParser/services/intentResolver.js`
- Test: `__tests__/nlParser.intentResolver.test.js`

**Interfaces:**
- Consumes: `matchItemByName` (Task 1), `detectAnswers` (Task 3).
- Produces:
  - `resolveIntent(normalized, { rawText, inventoryItems })` → `{ classification: 'resale'|'business_use'|'long_term_asset'|'sale_of_stock'|null, matchedItem: {item,confidence,matchType}|null, itemConsent: boolean|null, needsClassificationQuestion: boolean, needsItemConsent: boolean, needsQuantity: boolean }`
  - `buildInventoryBlock(normalized, resolution)` → `{ mode: 'none' } | { mode: 'existing', itemId, itemName, quantity, unit, unitCostPrice, currentStock } | { mode: 'create', itemName, quantity, unit, unitCostPrice }`
  - `PURCHASE_FAMILY`, `INTENT_TO_TYPE` constants (used by Task 8).

- [ ] **Step 1: Write the failing test**

```js
// __tests__/nlParser.intentResolver.test.js
'use strict';
const { resolveIntent, buildInventoryBlock, INTENT_TO_TYPE } = require('../services/nlParser/services/intentResolver');
const { ANSWER_OPTIONS } = require('../services/nlParser/constants/clarificationAnswers');

const ITEMS = [{ _id: 'i1', name: 'Rice (bag)', unit: 'bags', unitCostPrice: 480, currentStock: 12 }];

const base = (over = {}) => ({
  transactionType: 'expense', amount: 5000, lineItems: [], purchaseIntent: null,
  saleAffectsStock: false, ...over,
});

describe('resolveIntent — purchase decision table', () => {
  test('row 1: item matches existing inventory → resale, no question', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }] }),
      { rawText: 'bought 10 bags of rice for 5000', inventoryItems: ITEMS }
    );
    expect(r.classification).toBe('resale');
    expect(r.matchedItem.item._id).toBe('i1');
    expect(r.needsClassificationQuestion).toBe(false);
  });

  test('row 2: explicit resale cue ("stock") → resale even with no match', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'diesel', quantity: 100, unit: 'litres', unitPrice: 50 }] }),
      { rawText: 'bought diesel stock for the shop 5000', inventoryItems: ITEMS }
    );
    expect(r.classification).toBe('resale');
  });

  test('row 3: asset intent from the AI → long_term_asset', () => {
    const r = resolveIntent(
      base({ purchaseIntent: 'long_term_asset', lineItems: [{ name: 'office chair', quantity: 2, unit: 'units', unitPrice: 2500 }] }),
      { rawText: 'bought 2 office chairs for 5000', inventoryItems: ITEMS }
    );
    expect(r.classification).toBe('long_term_asset');
  });

  test('row 4: business tracks NO stock and no cues → business_use, no question', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'paper', quantity: 10, unit: 'reams', unitPrice: 500 }] }),
      { rawText: 'bought 10 reams of paper for 5000', inventoryItems: [] }
    );
    expect(r.classification).toBe('business_use');
    expect(r.needsClassificationQuestion).toBe(false);
  });

  test('row 5: tracks stock + goods parsed + no match + AI unsure → ASK', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }] }),
      { rawText: 'bought 20 bags of flour for 5000', inventoryItems: ITEMS }
    );
    expect(r.classification).toBeNull();
    expect(r.needsClassificationQuestion).toBe(true);
  });

  test('user answer beats everything', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }] }),
      { rawText: `bought flour\n\nAdditional details:\n- Q ${ANSWER_OPTIONS.BUSINESS_USE}`, inventoryItems: ITEMS }
    );
    expect(r.classification).toBe('business_use');
    expect(r.needsClassificationQuestion).toBe(false);
  });
});

describe('resolveIntent — item consent + quantity follow-ups', () => {
  test('resale + no match + no consent yet → needsItemConsent', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }] }),
      { rawText: `bought flour stock`, inventoryItems: ITEMS }
    );
    expect(r.classification).toBe('resale');
    expect(r.needsItemConsent).toBe(true);
  });

  test('consent yes + quantity missing → needsQuantity', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'flour', quantity: null, unit: null, unitPrice: null }] }),
      { rawText: `bought flour stock\n\nAdditional details:\n- Add? ${ANSWER_OPTIONS.ADD_ITEM_YES}`, inventoryItems: ITEMS }
    );
    expect(r.itemConsent).toBe(true);
    expect(r.needsItemConsent).toBe(false);
    expect(r.needsQuantity).toBe(true);
  });

  test('consent no → no follow-ups, records without stock tracking', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }] }),
      { rawText: `bought flour stock\n\nAdditional details:\n- Add? ${ANSWER_OPTIONS.ADD_ITEM_NO}`, inventoryItems: ITEMS }
    );
    expect(r.needsItemConsent).toBe(false);
    expect(r.needsQuantity).toBe(false);
  });

  test('matched item + quantity missing → needsQuantity', () => {
    const r = resolveIntent(
      base({ lineItems: [{ name: 'rice', quantity: null, unit: null, unitPrice: null }] }),
      { rawText: 'bought rice for 5000', inventoryItems: ITEMS }
    );
    expect(r.needsQuantity).toBe(true);
  });
});

describe('resolveIntent — sales', () => {
  test('sale of a matched item → sale_of_stock', () => {
    const r = resolveIntent(
      base({ transactionType: 'inventory_sale', saleAffectsStock: true,
             lineItems: [{ name: 'rice', quantity: 5, unit: 'bags', unitPrice: 800 }] }),
      { rawText: 'sold 5 bags of rice for 4000', inventoryItems: ITEMS }
    );
    expect(r.classification).toBe('sale_of_stock');
    expect(r.matchedItem.item._id).toBe('i1');
  });

  test('service income never touches stock', () => {
    const r = resolveIntent(
      base({ transactionType: 'income', saleAffectsStock: false }),
      { rawText: 'received 25000 for consulting', inventoryItems: ITEMS }
    );
    expect(r.classification).toBeNull();
  });
});

describe('buildInventoryBlock', () => {
  test('matched purchase → mode existing with item linkage', () => {
    const normalized = base({ lineItems: [{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }] });
    const r = resolveIntent(normalized, { rawText: 'bought 10 bags rice 5000', inventoryItems: ITEMS });
    const inv = buildInventoryBlock(normalized, r);
    expect(inv).toEqual({
      mode: 'existing', itemId: 'i1', itemName: 'Rice (bag)', quantity: 10,
      unit: 'bags', unitCostPrice: 500, currentStock: 12,
    });
  });

  test('consented new item → mode create', () => {
    const normalized = base({ lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }] });
    const r = resolveIntent(normalized, {
      rawText: `bought flour stock\n\nAdditional details:\n- Add? ${ANSWER_OPTIONS.ADD_ITEM_YES}`,
      inventoryItems: ITEMS,
    });
    const inv = buildInventoryBlock(normalized, r);
    expect(inv).toEqual({ mode: 'create', itemName: 'flour', quantity: 20, unit: 'bags', unitCostPrice: 250 });
  });

  test('business_use → mode none', () => {
    const normalized = base({ lineItems: [{ name: 'paper', quantity: 10, unit: 'reams', unitPrice: 500 }] });
    const r = resolveIntent(normalized, { rawText: 'bought paper', inventoryItems: [] });
    expect(buildInventoryBlock(normalized, r)).toEqual({ mode: 'none' });
  });
});

describe('INTENT_TO_TYPE', () => {
  test('maps every purchase classification to an NL transaction type', () => {
    expect(INTENT_TO_TYPE).toEqual({
      resale: 'inventory_purchase', business_use: 'expense', long_term_asset: 'asset_purchase',
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest __tests__/nlParser.intentResolver.test.js --silent`
Expected: FAIL — `Cannot find module`.

- [ ] **Step 3: Write the implementation**

```js
// services/nlParser/services/intentResolver.js
//
// Deterministic, DB-free "why was this bought?" resolver. The AI supplies
// signals (lineItems, purchaseIntent); THIS module decides — using the live
// item catalog and the user's own words — and says when the one plain
// clarifying question is genuinely needed. Decision table lives in the spec:
// docs/superpowers/specs/2026-07-11-smart-transaction-entry-design.md §2.
'use strict';
const { matchItemByName } = require('../../../utils/itemMatcher');
const { detectAnswers } = require('../constants/clarificationAnswers');

const PURCHASE_FAMILY = new Set(['expense', 'inventory_purchase', 'asset_purchase', 'gst_exclusive_purchase']);
const SALE_FAMILY = new Set(['income', 'inventory_sale', 'gst_inclusive_sale', 'gst_exclusive_sale']);
const INTENT_TO_TYPE = Object.freeze({
  resale: 'inventory_purchase',
  business_use: 'expense',
  long_term_asset: 'asset_purchase',
});

const RESALE_CUES = /\b(for sale|to sell|resale|resell|stock|inventory|maal)\b/i;
const ITEM_MATCH_MIN_CONFIDENCE = 0.75; // exact or single-substring fuzzy only

/**
 * @param {object} normalized  output of normalizeExtraction (needs transactionType,
 *                             lineItems, purchaseIntent, saleAffectsStock)
 * @param {{rawText?: string, inventoryItems?: Array}} ctx
 */
function resolveIntent(normalized, { rawText = '', inventoryItems = [] } = {}) {
  const answers = detectAnswers(rawText);
  const lineItems = normalized.lineItems || [];
  const primaryItem = lineItems[0] || null;
  const isPurchase = PURCHASE_FAMILY.has(normalized.transactionType);
  const isSale = SALE_FAMILY.has(normalized.transactionType);

  const result = {
    classification: null,
    matchedItem: null,
    itemConsent: answers.itemConsent,
    needsClassificationQuestion: false,
    needsItemConsent: false,
    needsQuantity: false,
  };
  if (!isPurchase && !isSale) return result;

  if (primaryItem) {
    const m = matchItemByName(inventoryItems, primaryItem.name);
    if (m.item && m.confidence >= ITEM_MATCH_MIN_CONFIDENCE) result.matchedItem = m;
  }

  if (isSale) {
    if (result.matchedItem || normalized.saleAffectsStock) {
      // Only a matched item can actually move stock — an unmatched "sale of
      // goods" records revenue only (you can't decrement stock you never tracked).
      if (result.matchedItem) {
        result.classification = 'sale_of_stock';
        if (!(primaryItem?.quantity > 0)) result.needsQuantity = true;
      }
    }
    return result;
  }

  // ── Purchases: decision table, first match wins ──────────────────────────
  if (answers.intentAnswer) {
    result.classification = answers.intentAnswer;             // user's answer beats everything
  } else if (result.matchedItem) {
    result.classification = 'resale';                          // row 1
  } else if (RESALE_CUES.test(rawText)) {
    result.classification = 'resale';                          // row 2
  } else if (normalized.purchaseIntent === 'long_term_asset' || normalized.transactionType === 'asset_purchase') {
    result.classification = 'long_term_asset';                 // row 3
  } else if (inventoryItems.length === 0) {
    result.classification = 'business_use';                    // row 4
  } else if (primaryItem && !normalized.purchaseIntent) {
    result.needsClassificationQuestion = true;                 // row 5 — genuinely torn
  } else {
    result.classification = normalized.purchaseIntent || 'business_use'; // row 6
  }

  // ── Resale follow-ups: consent-first item creation, then quantity ────────
  if (result.classification === 'resale') {
    if (!result.matchedItem && primaryItem && result.itemConsent === null) {
      result.needsItemConsent = true;
    }
    const stockWillMove = result.matchedItem || result.itemConsent === true;
    if (stockWillMove && !(primaryItem?.quantity > 0)) {
      result.needsQuantity = true;
    }
  }
  return result;
}

/**
 * Shape the preview's inventory block from a finished resolution.
 * mode 'create' requires explicit prior consent — ask-first, never silent.
 */
function buildInventoryBlock(normalized, r) {
  const li = (normalized.lineItems || [])[0] || null;
  const quantity = li?.quantity || null;
  if (r.classification === 'sale_of_stock' || (r.classification === 'resale' && r.matchedItem)) {
    if (!r.matchedItem) return { mode: 'none' };
    return {
      mode: 'existing',
      itemId: String(r.matchedItem.item._id),
      itemName: r.matchedItem.item.name,
      quantity,
      unit: li?.unit || r.matchedItem.item.unit || 'units',
      unitCostPrice: li?.unitPrice ?? r.matchedItem.item.unitCostPrice ?? null,
      currentStock: r.matchedItem.item.currentStock ?? null,
    };
  }
  if (r.classification === 'resale' && r.itemConsent === true && li) {
    return {
      mode: 'create',
      itemName: li.name,
      quantity,
      unit: li.unit || 'units',
      unitCostPrice: li.unitPrice ?? null,
    };
  }
  return { mode: 'none' };
}

module.exports = { resolveIntent, buildInventoryBlock, PURCHASE_FAMILY, SALE_FAMILY, INTENT_TO_TYPE };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest __tests__/nlParser.intentResolver.test.js --silent`
Expected: PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
git add services/nlParser/services/intentResolver.js __tests__/nlParser.intentResolver.test.js
git commit -m "feat(nl): deterministic purchase-intent resolver — decide from context, ask only when torn"
```

---

### Task 7: Clarification loop — three new questions, round cap 3 (backend)

**Files:**
- Modify: `services/nlParser/utils/clarificationBuilder.js`
- Test: `__tests__/nlParser.clarificationSequence.test.js`

**Interfaces:**
- Consumes: `ANSWER_OPTIONS` (Task 3); resolver output via new `opts.intentResolution` (Task 6).
- Produces: `buildClarification(confidence, parsedData, { attempt, maxRounds, intentResolution })`. New question `field` values (frontend re-uses the generic loop, no frontend change needed): `'purchaseIntent'`, `'newItemConsent'`, `'inventoryQuantity'`, `'vendorName'`. `DEFAULT_MAX_ROUNDS` becomes 3.

**Question priority (one per round):** amount → payment source → purchase-intent → new-item consent → quantity → vendor-for-credit → account purpose.

- [ ] **Step 1: Write the failing test**

```js
// __tests__/nlParser.clarificationSequence.test.js
'use strict';
const { buildClarification, DEFAULT_MAX_ROUNDS } = require('../services/nlParser/utils/clarificationBuilder');
const { ANSWER_OPTIONS } = require('../services/nlParser/constants/clarificationAnswers');

const CONF = { overall: 0.9, intent: 0.9, amount: 0.9, date: 0.9, accountMapping: 0.9 };
const DATA = {
  amount: 5000, paymentMethod: 'cash', cashFlowDirection: 'outflow',
  lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }],
  counterpartyName: null, creditAccount: null,
};

describe('clarification sequencing — smart entry', () => {
  test('round cap is now 3', () => {
    expect(DEFAULT_MAX_ROUNDS).toBe(3);
  });

  test('classification question fires with the three canonical options', () => {
    const c = buildClarification(CONF, DATA, {
      attempt: 0,
      intentResolution: { needsClassificationQuestion: true, needsItemConsent: false, needsQuantity: false },
    });
    expect(c.field).toBe('purchaseIntent');
    expect(c.options).toEqual([ANSWER_OPTIONS.RESALE, ANSWER_OPTIONS.BUSINESS_USE, ANSWER_OPTIONS.ASSET]);
  });

  test('item consent question names the item and offers yes/no literals', () => {
    const c = buildClarification(CONF, DATA, {
      attempt: 1,
      intentResolution: { needsClassificationQuestion: false, needsItemConsent: true, needsQuantity: false },
    });
    expect(c.field).toBe('newItemConsent');
    expect(c.question).toContain('flour');
    expect(c.options).toEqual([ANSWER_OPTIONS.ADD_ITEM_YES, ANSWER_OPTIONS.ADD_ITEM_NO]);
  });

  test('quantity question is free-text (no options)', () => {
    const c = buildClarification(CONF, DATA, {
      attempt: 1,
      intentResolution: { needsClassificationQuestion: false, needsItemConsent: false, needsQuantity: true },
    });
    expect(c.field).toBe('inventoryQuantity');
    expect(c.options).toBeUndefined();
  });

  test('vendor question fires for a credit purchase without a counterparty', () => {
    const c = buildClarification(CONF, { ...DATA, creditAccount: 'Accounts Payable' }, {
      attempt: 0,
      intentResolution: { needsClassificationQuestion: false, needsItemConsent: false, needsQuantity: false },
    });
    expect(c.field).toBe('vendorName');
  });

  test('amount still wins over everything', () => {
    const c = buildClarification(CONF, { ...DATA, amount: null }, {
      attempt: 0,
      intentResolution: { needsClassificationQuestion: true },
    });
    expect(c.field).toBe('amount');
  });

  test('round cap still terminates the loop', () => {
    const c = buildClarification(CONF, DATA, {
      attempt: 3,
      intentResolution: { needsClassificationQuestion: true },
    });
    expect(c).toBeNull();
  });

  test('nothing needed → null (no intentResolution supplied)', () => {
    expect(buildClarification(CONF, DATA, { attempt: 0 })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest __tests__/nlParser.clarificationSequence.test.js --silent`
Expected: FAIL — round cap is 2, new fields missing.

- [ ] **Step 3: Implement**

Replace the body of `services/nlParser/utils/clarificationBuilder.js` from `const DEFAULT_MAX_ROUNDS` down to the final `return null;` with:

```js
const { ANSWER_OPTIONS } = require('../constants/clarificationAnswers');

const DEFAULT_MAX_ROUNDS = 3;

function buildClarification(confidence = {}, parsedData = {}, opts = {}) {
  const attempt = Number(opts.attempt) || 0;
  const maxRounds = Number(opts.maxRounds) || DEFAULT_MAX_ROUNDS;
  const ir = opts.intentResolution || null;

  // Never loop forever — after the cap, fill the form with what we have.
  if (attempt >= maxRounds) return null;

  // 1) Amount is the single most important field — ask for it first.
  const amount = Number(parsedData.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return {
      field: 'amount',
      question: 'How much was this for? Please enter the amount.',
    };
  }

  // 2) Ambiguous payment source — but ONLY for money-moving transactions.
  const isCashFlow = parsedData.cashFlowDirection !== 'non_cash';
  if (isCashFlow && !parsedData.paymentMethod && !parsedData.sourceAccount) {
    return {
      field: 'paymentMethod',
      question: 'How was this paid?',
      options: ['Cash', 'Bank transfer', 'Credit/Debit card', 'On credit (pay later)'],
    };
  }

  // 3) Stock or expense? Only when the intent resolver was genuinely torn.
  if (ir?.needsClassificationQuestion) {
    return {
      field: 'purchaseIntent',
      question: 'Will you sell this again, or use it in the business?',
      options: [ANSWER_OPTIONS.RESALE, ANSWER_OPTIONS.BUSINESS_USE, ANSWER_OPTIONS.ASSET],
    };
  }

  // 4) Ask-first before creating a new inventory item (never silent).
  if (ir?.needsItemConsent) {
    const itemName = parsedData.lineItems?.[0]?.name || 'This item';
    return {
      field: 'newItemConsent',
      question: `"${itemName}" isn't in your inventory yet. Add it as a new item?`,
      options: [ANSWER_OPTIONS.ADD_ITEM_YES, ANSWER_OPTIONS.ADD_ITEM_NO],
    };
  }

  // 5) Stock will move but we don't know by how much.
  if (ir?.needsQuantity) {
    const verb = parsedData.cashFlowDirection === 'inflow' ? 'sell' : 'buy';
    return {
      field: 'inventoryQuantity',
      question: `How many did you ${verb}, and in what unit? (for example: 10 bags)`,
    };
  }

  // 6) A credit purchase needs to know who is owed.
  if (/accounts payable/i.test(parsedData.creditAccount || '') && !parsedData.counterpartyName) {
    return {
      field: 'vendorName',
      question: 'Who did you buy this from? (the supplier\'s name)',
    };
  }

  // 7) We could not confidently tell which accounts this belongs to.
  if ((confidence.accountMapping ?? 1) < 0.7) {
    return {
      field: 'purpose',
      question: 'What was this for? For example: office rent, a sale to a customer, or buying stock.',
    };
  }

  return null;
}

module.exports = { buildClarification, DEFAULT_MAX_ROUNDS };
```

- [ ] **Step 4: Run tests**

Run: `npx jest __tests__/nlParser.clarificationSequence.test.js __tests__/nlParser.hardening-step6.test.js --silent`
Expected: ALL PASS. (If an existing test pins `DEFAULT_MAX_ROUNDS === 2`, update that expectation to 3 — the cap raise is intentional.)

- [ ] **Step 5: Commit**

```bash
git add services/nlParser/utils/clarificationBuilder.js __tests__/nlParser.clarificationSequence.test.js
git commit -m "feat(nl): clarification loop learns stock/item/quantity/vendor questions, cap 3"
```

---

### Task 8: Pipeline integration — reclassification + inventory block in parsedData (backend)

**Files:**
- Modify: `services/nlParser/services/parserService.js` (`_finishParse`)
- Test: `__tests__/nlParser.smartEntryPipeline.test.js`

**Interfaces:**
- Consumes: `resolveIntent`, `buildInventoryBlock`, `INTENT_TO_TYPE`, `PURCHASE_FAMILY` (Task 6); `CASH_FLOW_MAP` from `constants/transactionTypes`.
- Produces: `parsedData` gains `lineItems`, `purchaseIntent`, `saleAffectsStock`, `inventory` (block from Task 6). Purchase-family `transactionType` is **reclassified to match the resolved intent before journal generation**; `debitAccount` hints follow the classification. `buildClarification` receives `intentResolution`.

- [ ] **Step 1: Write the failing test**

The pipeline test mocks the AI call and runs the real pipeline (same pattern as `__tests__/nlParser.phase3.test.js`):

```js
// __tests__/nlParser.smartEntryPipeline.test.js
'use strict';
jest.mock('../services/nlParser/services/aiExtractionService', () => ({
  callAIExtraction: jest.fn(),
  callAIVision: jest.fn(),
}));
const { callAIExtraction } = require('../services/nlParser/services/aiExtractionService');
const { parseTransaction } = require('../services/nlParser/services/parserService');
const { ANSWER_OPTIONS } = require('../services/nlParser/constants/clarificationAnswers');

const ITEMS = [{ _id: 'i1', name: 'Rice (bag)', unit: 'bags', unitCostPrice: 480, currentStock: 12 }];
const CONF = { intent: 0.95, amount: 0.95, date: 0.95, accountMapping: 0.95 };

const extraction = (over = {}) => ({
  intent: 'purchase', transactionType: 'expense', subcategory: null, amount: 5000,
  currency: 'PKR', date: '2026-07-10', description: 'Bought goods',
  counterpartyName: null, paymentMethod: 'cash', sourceAccount: 'Cash in Hand',
  debitAccount: 'General Expenses', creditAccount: 'Cash in Hand',
  cashFlowDirection: 'outflow', lineItems: [], purchaseIntent: null,
  saleAffectsStock: false, isInstallment: false, confidence: CONF, ...over,
});

describe('smart entry pipeline', () => {
  beforeEach(() => jest.clearAllMocks());

  test('matched item reclassifies expense → inventory_purchase and links the item', async () => {
    callAIExtraction.mockResolvedValue(extraction({
      lineItems: [{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }],
    }));
    const r = await parseTransaction('bought 10 bags of rice for 5000 cash', [], { inventoryItems: ITEMS });
    expect(r.parsedData.transactionType).toBe('inventory_purchase');
    expect(r.parsedData.inventory).toMatchObject({ mode: 'existing', itemId: 'i1', quantity: 10 });
    expect(r.needsClarification).toBe(false);
  });

  test('the word "inventory" alone no longer forces stock: business_use answer reroutes to expense', async () => {
    callAIExtraction.mockResolvedValue(extraction({
      transactionType: 'inventory_purchase', debitAccount: 'Inventory',
      lineItems: [{ name: 'printer paper', quantity: 10, unit: 'reams', unitPrice: 500 }],
    }));
    const raw = `bought inventory of printer paper 5000\n\nAdditional details:\n- Q ${ANSWER_OPTIONS.BUSINESS_USE}`;
    const r = await parseTransaction(raw, [], { inventoryItems: ITEMS });
    expect(r.parsedData.transactionType).toBe('expense');
    expect(r.parsedData.inventory.mode).toBe('none');
    // the Inventory debit hint must not survive a business_use classification
    expect(r.parsedData.debitAccount || '').not.toMatch(/inventory/i);
  });

  test('unknown goods + tracked stock + unsure AI → asks the classification question', async () => {
    callAIExtraction.mockResolvedValue(extraction({
      lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }],
    }));
    const r = await parseTransaction('bought 20 bags of flour for 5000 cash', [], { inventoryItems: ITEMS });
    expect(r.needsClarification).toBe(true);
    expect(r.clarification.field).toBe('purchaseIntent');
  });

  test('consented creation lands in parsedData.inventory as mode create', async () => {
    callAIExtraction.mockResolvedValue(extraction({
      lineItems: [{ name: 'flour', quantity: 20, unit: 'bags', unitPrice: 250 }],
    }));
    const raw = `bought 20 bags of flour stock for 5000 cash\n\nAdditional details:\n- Add? ${ANSWER_OPTIONS.ADD_ITEM_YES}`;
    const r = await parseTransaction(raw, [], { inventoryItems: ITEMS });
    expect(r.parsedData.transactionType).toBe('inventory_purchase');
    expect(r.parsedData.inventory).toMatchObject({ mode: 'create', itemName: 'flour', quantity: 20 });
  });

  test('resale classification steers the debit hint to Inventory', async () => {
    callAIExtraction.mockResolvedValue(extraction({
      lineItems: [{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }],
    }));
    const r = await parseTransaction('bought 10 bags of rice for 5000 cash', [], { inventoryItems: ITEMS });
    expect(r.parsedData.debitAccount).toBe('Inventory');
  });

  test('sale of matched stock exposes inventory for the COGS path', async () => {
    callAIExtraction.mockResolvedValue(extraction({
      transactionType: 'inventory_sale', cashFlowDirection: 'inflow', saleAffectsStock: true,
      debitAccount: 'Cash in Hand', creditAccount: 'Sales Revenue',
      lineItems: [{ name: 'rice', quantity: 5, unit: 'bags', unitPrice: 800 }], amount: 4000,
    }));
    const r = await parseTransaction('sold 5 bags of rice for 4000 cash', [], { inventoryItems: ITEMS });
    expect(r.parsedData.inventory).toMatchObject({ mode: 'existing', itemId: 'i1', quantity: 5 });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest __tests__/nlParser.smartEntryPipeline.test.js --silent`
Expected: FAIL — `parsedData.inventory` undefined, no reclassification.

- [ ] **Step 3: Implement**

In `services/nlParser/services/parserService.js`:

3a. Add imports at the top:

```js
const { resolveIntent, buildInventoryBlock, PURCHASE_FAMILY, INTENT_TO_TYPE } = require('./intentResolver');
const { CASH_FLOW_MAP } = require('../constants/transactionTypes');
```

3b. In `_finishParse`, immediately after the normalization step (line 53), insert:

```js
  // ── Step 2.5: Intent resolution — decide WHY the thing was bought ─────────
  // Deterministic: live item catalog + the user's own words beat the AI's
  // keyword guess. Runs BEFORE journal generation so the journal template
  // matches the resolved classification, not the original phrasing.
  const intentResolution = resolveIntent(normalized, {
    rawText: rawInput,
    inventoryItems: opts.inventoryItems || [],
  });
  if (
    intentResolution.classification &&
    INTENT_TO_TYPE[intentResolution.classification] &&
    PURCHASE_FAMILY.has(normalized.transactionType) &&
    normalized.transactionType !== 'gst_exclusive_purchase' && // tax template owns its journal
    normalized.transactionType !== INTENT_TO_TYPE[intentResolution.classification]
  ) {
    normalized.transactionType = INTENT_TO_TYPE[intentResolution.classification];
    normalized.cashFlowDirection = CASH_FLOW_MAP[normalized.transactionType] || normalized.cashFlowDirection;
  }
  // Debit hint follows the classification — never let a stale suggestion
  // point stock at an expense account or supplies at Inventory.
  if (intentResolution.classification === 'resale') {
    normalized.debitAccount = 'Inventory';
  } else if (
    intentResolution.classification === 'business_use' &&
    /inventory|stock/i.test(normalized.debitAccount || '')
  ) {
    normalized.debitAccount = null; // journal generator falls back to the subcategory template
  }
  normalized.inventory = buildInventoryBlock(normalized, intentResolution);
```

3c. Change the `buildClarification` call (line 96) to pass the resolution:

```js
  const clarification = buildClarification(confidence, normalized, {
    attempt: opts.attempt || 0,
    intentResolution,
  });
```

3d. Add the new fields to the `parsedData` object (after `eobi:` line 141):

```js
    // Smart entry — goods, intent, and the inventory linkage block
    lineItems:        normalized.lineItems,
    purchaseIntent:   normalized.purchaseIntent,
    saleAffectsStock: normalized.saleAffectsStock,
    inventory:        normalized.inventory,
```

- [ ] **Step 4: Run tests**

Run: `npx jest __tests__/nlParser.smartEntryPipeline.test.js __tests__/nlParser.phase3.test.js __tests__/nlParser.tax-liability-inventory.test.js --silent`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add services/nlParser/services/parserService.js __tests__/nlParser.smartEntryPipeline.test.js
git commit -m "feat(nl): pipeline reclassifies purchases by resolved intent + emits inventory block"
```

---

### Task 9: Preview endpoint — inventory context, guardrails, auto-post gates (backend)

**Files:**
- Modify: `utils/nlParserPreview.helper.js` (`mapParserToPreview` passthrough)
- Modify: `controllers/transaction.controller.js:248-407` (`processNaturalLanguage`)
- Test: `tests/unit/controllers/transaction.nlPreviewInventory.test.js`

**Interfaces:**
- Consumes: `parsedData.inventory` / `lineItems` (Task 8), `checkJournalShape` (Task 2).
- Produces: preview response gains `inventory` (`{ mode, itemId?, itemName?, quantity?, unit?, unitCostPrice?, currentStock? }`), `lineItems`, `guardrail: { ok, violations }`. Auto-post: blocked when `guardrail.ok === false`, when `inventory.mode === 'create'`, or when `inventory.mode === 'existing'` without a positive quantity; when mode `existing` **with** quantity, `inventoryItemId` + `inventoryQty` ride the auto-posted transaction so stock syncs.

- [ ] **Step 1: Write the failing test**

Model the mock scaffolding on `tests/unit/controllers/transaction.controller.test.js` (same require paths, `../../..` prefix). Core assertions:

```js
// tests/unit/controllers/transaction.nlPreviewInventory.test.js
'use strict';
jest.mock('../../../services/nlParser/services/parserService', () => ({ parseTransaction: jest.fn() }));
jest.mock('../../../repositories/account.repository', () => ({
  findByBusiness: jest.fn(), findByBusinessAndName: jest.fn(),
}));
jest.mock('../../../repositories/business.repository', () => ({ findById: jest.fn() }));
jest.mock('../../../models/InventoryItem.model', () => ({ find: jest.fn() }));
jest.mock('../../../services/learnedResolution.service', () => ({
  recallAccounts: jest.fn().mockResolvedValue(null),
  learnAccountsFromConfirmation: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('../../../services/aiDecision.service', () => ({
  record: jest.fn().mockResolvedValue({ _id: 'dec1' }),
  recordOutcome: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('../../../services/approval.service', () => ({ submitOrPost: jest.fn() }));
jest.mock('../../../config/logger', () => ({ info: jest.fn(), warn: jest.fn(), error: jest.fn() }));

const parserService = require('../../../services/nlParser/services/parserService');
const accountRepository = require('../../../repositories/account.repository');
const businessRepository = require('../../../repositories/business.repository');
const InventoryItem = require('../../../models/InventoryItem.model');
const approvalService = require('../../../services/approval.service');

// NOTE: adjust this import to however the existing controller test file
// requires the controller and extracts processNaturalLanguage.
const { processNaturalLanguage } = require('../../../controllers/transaction.controller');

const ACCOUNTS = [
  { _id: 'a-inv',  accountName: 'Inventory',      accountType: 'Asset' },
  { _id: 'a-cash', accountName: 'Cash in Hand',   accountType: 'Asset' },
  { _id: 'a-rev',  accountName: 'Sales Revenue',  accountType: 'Revenue' },
];

const mkRes = () => {
  const res = { status: jest.fn().mockReturnThis(), json: jest.fn().mockReturnThis() };
  return res;
};
const mkReq = (body) => ({ body, user: { businessId: 'biz1', id: 'u1' }, ip: '127.0.0.1' });

const parsedResult = (over = {}) => ({
  success: true,
  parsedData: {
    transactionType: 'inventory_purchase', amount: 5000, isInstallment: false,
    inventory: { mode: 'existing', itemId: 'i1', itemName: 'Rice (bag)', quantity: 10, unit: 'bags', unitCostPrice: 500, currentStock: 12 },
    lineItems: [{ name: 'rice', quantity: 10, unit: 'bags', unitPrice: 500 }],
    ...over.parsedData,
  },
  journalEntries: [
    { entryType: 'debit', account: 'Inventory', amount: 5000 },
    { entryType: 'credit', account: 'Cash in Hand', amount: 5000 },
  ],
  confidence: { overall: 0.99, intent: 0.99, amount: 0.99, date: 0.99, accountMapping: 0.99 },
  accountResolution: {
    debit: { account: ACCOUNTS[0], confidence: 1, matchType: 'exact' },
    credit: { account: ACCOUNTS[1], confidence: 1, matchType: 'exact' },
  },
  requiresReview: false, reviewReasons: [], clarification: null, needsClarification: false,
  ...over,
});

beforeEach(() => {
  jest.clearAllMocks();
  accountRepository.findByBusiness.mockResolvedValue(ACCOUNTS);
  InventoryItem.find.mockReturnValue({
    select: jest.fn().mockReturnThis(), limit: jest.fn().mockReturnThis(),
    lean: jest.fn().mockResolvedValue([{ _id: 'i1', name: 'Rice (bag)', unit: 'bags', unitCostPrice: 480, currentStock: 12 }]),
  });
  businessRepository.findById.mockResolvedValue({ aiSettings: { autoPostEnabled: true } });
  approvalService.submitOrPost.mockResolvedValue({ pendingApproval: false, transaction: { _id: 'tx1' } });
});

describe('processNaturalLanguage — inventory context + gates', () => {
  test('passes live inventory items into the parser', async () => {
    parserService.parseTransaction.mockResolvedValue(parsedResult());
    await processNaturalLanguage(mkReq({ text: 'bought 10 bags of rice for 5000 cash' }), mkRes(), jest.fn());
    const opts = parserService.parseTransaction.mock.calls[0][2];
    expect(opts.inventoryItems).toHaveLength(1);
    expect(opts.inventoryItems[0].name).toBe('Rice (bag)');
  });

  test('preview carries the inventory block through', async () => {
    parserService.parseTransaction.mockResolvedValue(parsedResult());
    businessRepository.findById.mockResolvedValue({ aiSettings: { autoPostEnabled: false } });
    const res = mkRes();
    await processNaturalLanguage(mkReq({ text: 'bought 10 bags of rice for 5000 cash' }), res, jest.fn());
    const payload = res.json.mock.calls[0][0];
    expect(payload.data.inventory).toMatchObject({ mode: 'existing', itemId: 'i1', quantity: 10 });
  });

  test('auto-post of a matched item CARRIES inventoryItemId + inventoryQty', async () => {
    parserService.parseTransaction.mockResolvedValue(parsedResult());
    await processNaturalLanguage(mkReq({ text: 'bought 10 bags of rice for 5000 cash' }), mkRes(), jest.fn());
    expect(approvalService.submitOrPost).toHaveBeenCalledTimes(1);
    const txData = approvalService.submitOrPost.mock.calls[0][0];
    expect(txData.inventoryItemId).toBe('i1');
    expect(txData.inventoryQty).toBe(10);
  });

  test('pending item creation hard-blocks auto-post', async () => {
    parserService.parseTransaction.mockResolvedValue(parsedResult({
      parsedData: { inventory: { mode: 'create', itemName: 'flour', quantity: 20, unit: 'bags', unitCostPrice: 250 } },
    }));
    await processNaturalLanguage(mkReq({ text: 'bought flour' }), mkRes(), jest.fn());
    expect(approvalService.submitOrPost).not.toHaveBeenCalled();
  });

  test('guardrail violation blocks auto-post and forces review', async () => {
    // AI suggested crediting Sales Revenue on a purchase — structurally wrong
    parserService.parseTransaction.mockResolvedValue(parsedResult({
      journalEntries: [
        { entryType: 'debit', account: 'Inventory', amount: 5000 },
        { entryType: 'credit', account: 'Sales Revenue', amount: 5000 },
      ],
      parsedData: { inventory: { mode: 'none' } },
    }));
    const res = mkRes();
    await processNaturalLanguage(mkReq({ text: 'bought rice, weird parse' }), res, jest.fn());
    expect(approvalService.submitOrPost).not.toHaveBeenCalled();
    const payload = res.json.mock.calls[0][0];
    expect(payload.data.requiresReview).toBe(true);
    expect(payload.data.guardrail.ok).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest tests/unit/controllers/transaction.nlPreviewInventory.test.js --silent`
Expected: FAIL — `opts.inventoryItems` undefined, no `inventory`/`guardrail` on preview. (If the controller's module-level requires pull in services not mocked above, add `jest.mock` lines for them following `tests/unit/controllers/transaction.controller.test.js` — extend mocks, don't weaken assertions.)

- [ ] **Step 3: Implement**

3a. `utils/nlParserPreview.helper.js` — in the return object of `mapParserToPreview` (after `invoiceNumber`, line 183):

```js
    // Smart entry — goods + inventory linkage for the confirm step
    lineItems:               parsedData.lineItems              || [],
    inventory:               parsedData.inventory              || { mode: 'none' },
```

3b. `controllers/transaction.controller.js` — in `processNaturalLanguage`:

After the `businessAccounts` load (line 263), add:

```js
    // Live inventory items → the parser matches goods names against real items.
    // Non-fatal: parsing proceeds itemless on failure.
    let inventoryItems = [];
    try {
      const InventoryItem = require('../models/InventoryItem.model');
      inventoryItems = await InventoryItem.find({ businessId: req.user.businessId, isActive: true })
        .select('name unit unitCostPrice currentStock')
        .limit(100)
        .lean();
    } catch (invErr) {
      logger.warn('NL parse: could not load inventory items (non-fatal):', invErr.message);
    }
```

Change the parse call (line 265) to:

```js
    const parsed = await parserService.parseTransaction(text, businessAccounts, {
      attempt: Number(attempt) || 0,
      inventoryItems,
    });
```

After the journal-lines resolution block (after line 339), add the guardrail check:

```js
    // ── Structural guardrail: a purchase can never debit Revenue etc. ────────
    const { checkJournalShape } = require('../utils/journalGuardrails');
    const typeOfAccount = (id) =>
      businessAccounts.find((a) => String(a._id) === String(id))?.accountType || null;
    const guardrail = checkJournalShape({
      transactionType:   preview.transactionType,
      debitAccountType:  typeOfAccount(preview.debitAccountId),
      creditAccountType: typeOfAccount(preview.creditAccountId),
    });
    preview.guardrail = guardrail;
    if (!guardrail.ok) {
      preview.requiresReview = true;
      preview.reviewReasons = [...new Set([...(preview.reviewReasons || []), ...guardrail.violations])];
    }
```

Change the auto-post gate condition (line 359) to:

```js
    const inventoryBlocksAutoPost =
      preview.inventory?.mode === 'create' ||
      (preview.inventory?.mode === 'existing' && !(preview.inventory.quantity > 0));
    if (
      preview.debitAccountId && preview.creditAccountId &&
      !parsed.parsedData?.isInstallment &&
      guardrail.ok && !inventoryBlocksAutoPost
    ) {
```

And inside `transactionData` (after `creditAccountId`, line 373), add:

```js
            ...(preview.inventory?.mode === 'existing' && preview.inventory.quantity > 0
              ? { inventoryItemId: preview.inventory.itemId, inventoryQty: preview.inventory.quantity }
              : {}),
```

- [ ] **Step 4: Run tests**

Run: `npx jest tests/unit/controllers/transaction.nlPreviewInventory.test.js tests/unit/controllers/transaction.controller.test.js --silent`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/nlParserPreview.helper.js controllers/transaction.controller.js tests/unit/controllers/transaction.nlPreviewInventory.test.js
git commit -m "feat(nl): preview carries inventory block; guardrails + item gates on auto-post"
```

---

### Task 10: Confirm path — CoA resolve-or-create + inventory forwarding (backend)

**Files:**
- Modify: `controllers/transaction.controller.js:36-52` (`resolveAccountIds`) and `confirmNaturalLanguage` (lines 416-518)
- Test: `tests/unit/controllers/transaction.nlConfirmInventory.test.js`

**Interfaces:**
- Consumes: `resolveForImport(businessId, accounts, rawName, ctx)` from `services/importAccountResolution.service.js` (existing — full name→code→synonym→create chain, catalog-shaped, race-safe).
- Produces: `resolveAccountIds(businessId, row, { transactionType, userId })` now falls through the full deterministic chain (creates catalog-shaped accounts instead of 400-ing on unknown names). `confirmNaturalLanguage` forwards `inventoryItemId`/`inventoryQty`/`newInventoryItem` into `transactionData`. `newInventoryItem` shape: `{ name: string, unit: string, quantity: number, unitCostPrice: number|null }`.

- [ ] **Step 1: Write the failing test**

```js
// tests/unit/controllers/transaction.nlConfirmInventory.test.js
'use strict';
jest.mock('../../../services/importAccountResolution.service', () => ({ resolveForImport: jest.fn() }));
jest.mock('../../../repositories/account.repository', () => ({
  findByBusiness: jest.fn(), findByBusinessAndName: jest.fn(),
}));
jest.mock('../../../services/approval.service', () => ({ submitOrPost: jest.fn() }));
jest.mock('../../../services/learnedResolution.service', () => ({
  recallAccounts: jest.fn().mockResolvedValue(null),
  learnAccountsFromConfirmation: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('../../../services/aiDecision.service', () => ({
  record: jest.fn().mockResolvedValue({ _id: 'dec1' }),
  recordOutcome: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('../../../config/logger', () => ({ info: jest.fn(), warn: jest.fn(), error: jest.fn() }));

const { resolveForImport } = require('../../../services/importAccountResolution.service');
const accountRepository = require('../../../repositories/account.repository');
const approvalService = require('../../../services/approval.service');
const { confirmNaturalLanguage } = require('../../../controllers/transaction.controller');

const mkRes = () => ({ status: jest.fn().mockReturnThis(), json: jest.fn().mockReturnThis() });
const mkReq = (body) => ({ body, user: { businessId: 'biz1', id: 'u1' }, ip: '127.0.0.1' });

beforeEach(() => {
  jest.clearAllMocks();
  accountRepository.findByBusiness.mockResolvedValue([]);
  approvalService.submitOrPost.mockResolvedValue({ pendingApproval: false, transaction: { _id: 'tx1' } });
});

describe('confirmNaturalLanguage — smart entry', () => {
  const BASE = {
    transactionDate: '2026-07-10', description: 'Stock purchase', transactionType: 'Inventory Purchase',
    amount: 5000, debitAccountId: 'a-inv', creditAccountId: 'a-cash',
  };

  test('forwards existing-item linkage into transactionData', async () => {
    await confirmNaturalLanguage(mkReq({ ...BASE, inventoryItemId: 'i1', inventoryQty: 10 }), mkRes(), jest.fn());
    const txData = approvalService.submitOrPost.mock.calls[0][0];
    expect(txData.inventoryItemId).toBe('i1');
    expect(txData.inventoryQty).toBe(10);
  });

  test('forwards a consented newInventoryItem (sanitized)', async () => {
    await confirmNaturalLanguage(mkReq({
      ...BASE,
      newInventoryItem: { name: '  Flour ', unit: 'bags', quantity: '20', unitCostPrice: 250 },
    }), mkRes(), jest.fn());
    const txData = approvalService.submitOrPost.mock.calls[0][0];
    expect(txData.newInventoryItem).toEqual({ name: 'Flour', unit: 'bags', quantity: 20, unitCostPrice: 250 });
  });

  test('unknown account NAME resolves through the deterministic chain instead of 400', async () => {
    resolveForImport.mockResolvedValue({ account: { _id: 'created-1', accountName: 'Inventory' }, created: true, how: 'created' });
    await confirmNaturalLanguage(mkReq({
      ...BASE, debitAccountId: undefined, debitAccount: 'Inventory',
    }), mkRes(), jest.fn());
    expect(resolveForImport).toHaveBeenCalledWith('biz1', expect.any(Array), 'Inventory',
      expect.objectContaining({ side: 'debit', transactionType: 'Inventory Purchase', userId: 'u1' }));
    const txData = approvalService.submitOrPost.mock.calls[0][0];
    expect(txData.debitAccountId).toBe('created-1');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest tests/unit/controllers/transaction.nlConfirmInventory.test.js --silent`
Expected: FAIL — inventory fields dropped; unknown name throws 400.

- [ ] **Step 3: Implement**

3a. Replace `resolveAccountIds` (controller lines 36-52) with:

```js
// Full deterministic chain (exact name → code → synonym → create-from-catalog
// shape) via the same service the bulk importer uses — an NL confirm can no
// longer fail just because the wording differs from the seeded chart.
const resolveAccountIds = async (businessId, row, { transactionType = null, userId = null } = {}) => {
  let debitAccountId = row.debitAccountId;
  let creditAccountId = row.creditAccountId;
  const debitName = row.debitAccountName || row.debitAccount;
  const creditName = row.creditAccountName || row.creditAccount;
  if ((debitAccountId || !debitName) && (creditAccountId || !creditName)) {
    return { debitAccountId, creditAccountId };
  }
  const { resolveForImport } = require('../services/importAccountResolution.service');
  const accounts = (await accountRepository.findByBusiness(businessId)) || [];
  if (!debitAccountId && debitName) {
    const r = await resolveForImport(businessId, accounts, debitName, { side: 'debit', transactionType, userId });
    if (!r.account) throw new ApiError(400, `Debit account not found: "${debitName}". Please check your Chart of Accounts.`);
    debitAccountId = r.account._id;
  }
  if (!creditAccountId && creditName) {
    const r = await resolveForImport(businessId, accounts, creditName, { side: 'credit', transactionType, userId });
    if (!r.account) throw new ApiError(400, `Credit account not found: "${creditName}". Please check your Chart of Accounts.`);
    creditAccountId = r.account._id;
  }
  return { debitAccountId, creditAccountId };
};
```

(Existing call sites pass only two arguments — the new options object defaults keep them working.)

3b. In `confirmNaturalLanguage`, change the resolve call (line 432) to:

```js
    const { debitAccountId, creditAccountId } = await resolveAccountIds(req.user.businessId, req.body, {
      transactionType: req.body.transactionType || null,
      userId: req.user.id,
    });
```

3c. Add to `transactionData` (after `inputMethod: 'nlp',` line 463):

```js
      // Smart entry — inventory linkage (existing item) or consented creation
      ...(req.body.inventoryItemId
        ? { inventoryItemId: req.body.inventoryItemId, inventoryQty: Number(req.body.inventoryQty) || 1 }
        : {}),
      ...(!req.body.inventoryItemId && req.body.newInventoryItem?.name
        ? {
            newInventoryItem: {
              name: String(req.body.newInventoryItem.name).trim().slice(0, 200),
              unit: String(req.body.newInventoryItem.unit || 'units').trim().slice(0, 30),
              quantity: Number(req.body.newInventoryItem.quantity),
              unitCostPrice: Number(req.body.newInventoryItem.unitCostPrice) > 0
                ? Number(req.body.newInventoryItem.unitCostPrice)
                : null,
            },
          }
        : {}),
```

- [ ] **Step 4: Run tests**

Run: `npx jest tests/unit/controllers/transaction.nlConfirmInventory.test.js tests/unit/controllers/transaction.controller.test.js --silent`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add controllers/transaction.controller.js tests/unit/controllers/transaction.nlConfirmInventory.test.js
git commit -m "feat(nl): confirm path resolves accounts via deterministic chain + forwards inventory linkage"
```

---

### Task 11: createTransaction — atomic new-item creation (backend)

**Files:**
- Modify: `services/transaction.service.js` — new block 7a-2 after block 7a (line 738), plus one-word change in `persist` (line 807)
- Test: `tests/unit/services/transaction.newInventoryItem.test.js`

**Interfaces:**
- Consumes: `data.newInventoryItem` (Task 10 shape), existing `inventoryService.applyPurchaseStock(businessId, itemId, qty, costPerUnit, { userId, session })`, existing `PURCHASE_TYPES_TRIGGERING_STOCK`.
- Produces: inside the persist session — link-or-create the item by exact name (idempotent under retry), apply purchase stock, stamp `inventoryItemId`/`inventoryQty` onto the created JournalEntry, and set `data.inventoryItemId` so the TRANSACTION_CREATED event carries it. `persist` now calls `sideEffect(txnSession, tx)` (second arg; existing single-arg closures unaffected).

- [ ] **Step 1: Write the failing test**

Copy the mock scaffolding header from `tests/unit/services/transaction.createAtomicity.test.js` (lines 14-63: the `jest.mock` calls for withTransaction, repositories, ChartOfAccount, audit/inventory/invoice/bill/partyBalance/taxEngine/AccountingPeriod/InvoiceCounter/logger — reproduce them verbatim), extending two mocks:

```js
jest.mock('../../../repositories/inventoryItem.repository', () => ({
  model: {
    findOne: jest.fn(),
    create: jest.fn(),
  },
}));
jest.mock('../../../models/JournalEntry.model', () => ({
  findOne: jest.fn().mockReturnValue({ lean: jest.fn().mockResolvedValue(null) }),
  updateOne: jest.fn().mockResolvedValue({}),
}));
```

Then the tests:

```js
const transactionService = require('../../../services/transaction.service');
const transactionRepository = require('../../../repositories/transaction.repository');
const accountRepository = require('../../../repositories/account.repository');
const inventoryItemRepository = require('../../../repositories/inventoryItem.repository');
const inventoryService = require('../../../services/inventory.service');
const JournalEntry = require('../../../models/JournalEntry.model');
const { TRANSACTION_TYPES } = require('../../../config/constants');

const makeAccount = (id) => ({ _id: id, normalBalance: 'Debit', accountName: 'X', accountType: 'Asset', runningBalance: 0 });
const CREATED_TX = {
  _id: 'tx1', businessId: 'biz1', transactionType: TRANSACTION_TYPES.INVENTORY_PURCHASE,
  amount: 5000, toObject: function () { return { ...this }; },
};

beforeEach(() => {
  jest.clearAllMocks();
  require('../../../services/audit.service').logCreate = jest.fn().mockResolvedValue(undefined);
  accountRepository.findOneByBusinessAndId.mockImplementation((_b, id) => Promise.resolve(makeAccount(id)));
  accountRepository.updateRunningBalance = accountRepository.updateRunningBalance || jest.fn();
  transactionRepository.createTransaction.mockResolvedValue(CREATED_TX);
  inventoryService.applyPurchaseStock.mockResolvedValue({});
  // no same-name item exists by default
  inventoryItemRepository.model.findOne.mockReturnValue({ session: jest.fn().mockResolvedValue(null) });
  inventoryItemRepository.model.create.mockResolvedValue([{ _id: 'new-item-1', name: 'Flour' }]);
});

const PURCHASE = {
  businessId: 'biz1', transactionDate: new Date().toISOString(), description: 'Stock purchase',
  transactionType: TRANSACTION_TYPES.INVENTORY_PURCHASE, amount: 5000,
  debitAccountId: 'a-inv', creditAccountId: 'a-cash', inputMethod: 'nlp',
  newInventoryItem: { name: 'Flour', unit: 'bags', quantity: 20, unitCostPrice: 250 },
};

describe('createTransaction — consented new inventory item', () => {
  test('creates the item, applies stock, stamps the JE — all in the persist session', async () => {
    await transactionService.createTransaction({ ...PURCHASE }, 'u1', '127.0.0.1');
    // item created within session
    expect(inventoryItemRepository.model.create).toHaveBeenCalledWith(
      [expect.objectContaining({ businessId: 'biz1', name: 'Flour', unit: 'bags', unitCostPrice: 0, currentStock: 0 })],
      { session: 'TXN-SESSION' }
    );
    // stock applied with cost from the consented card
    expect(inventoryService.applyPurchaseStock).toHaveBeenCalledWith(
      'biz1', 'new-item-1', 20, 250, expect.objectContaining({ session: 'TXN-SESSION' })
    );
    // linkage stamped on the created entry in the same session
    expect(JournalEntry.updateOne).toHaveBeenCalledWith(
      { _id: 'tx1' },
      { $set: { inventoryItemId: 'new-item-1', inventoryQty: 20 } },
      { session: 'TXN-SESSION' }
    );
  });

  test('same-name item already exists → LINKS instead of creating (retry-safe)', async () => {
    inventoryItemRepository.model.findOne.mockReturnValue({
      session: jest.fn().mockResolvedValue({ _id: 'existing-9', name: 'Flour' }),
    });
    await transactionService.createTransaction({ ...PURCHASE }, 'u1', '127.0.0.1');
    expect(inventoryItemRepository.model.create).not.toHaveBeenCalled();
    expect(inventoryService.applyPurchaseStock).toHaveBeenCalledWith(
      'biz1', 'existing-9', 20, 250, expect.anything()
    );
  });

  test('journal insert failure → NO item created, NO stock applied (atomicity)', async () => {
    transactionRepository.createTransaction.mockRejectedValue(new Error('insert failed'));
    await expect(
      transactionService.createTransaction({ ...PURCHASE }, 'u1', '127.0.0.1')
    ).rejects.toThrow('insert failed');
    expect(inventoryItemRepository.model.create).not.toHaveBeenCalled();
    expect(inventoryService.applyPurchaseStock).not.toHaveBeenCalled();
  });

  test('missing unitCostPrice derives cost from amount / quantity', async () => {
    await transactionService.createTransaction({
      ...PURCHASE, newInventoryItem: { name: 'Flour', unit: 'bags', quantity: 20, unitCostPrice: null },
    }, 'u1', '127.0.0.1');
    expect(inventoryService.applyPurchaseStock).toHaveBeenCalledWith(
      'biz1', 'new-item-1', 20, 250, expect.anything()  // 5000 / 20
    );
  });

  test('rejects a nameless or zero-quantity newInventoryItem', async () => {
    await expect(transactionService.createTransaction({
      ...PURCHASE, newInventoryItem: { name: ' ', unit: 'bags', quantity: 20 },
    }, 'u1', '127.0.0.1')).rejects.toThrow(/name/i);
    await expect(transactionService.createTransaction({
      ...PURCHASE, newInventoryItem: { name: 'Flour', unit: 'bags', quantity: 0 },
    }, 'u1', '127.0.0.1')).rejects.toThrow(/quantity/i);
  });

  test('existing inventoryItemId takes precedence — newInventoryItem ignored', async () => {
    await transactionService.createTransaction({
      ...PURCHASE, inventoryItemId: 'i1', inventoryQty: 10,
      newInventoryItem: { name: 'Flour', unit: 'bags', quantity: 20, unitCostPrice: 250 },
    }, 'u1', '127.0.0.1');
    expect(inventoryItemRepository.model.create).not.toHaveBeenCalled();
    // block 7a handles the existing item path
    expect(inventoryService.applyPurchaseStock).toHaveBeenCalledWith(
      'biz1', 'i1', 10, expect.any(Number), expect.anything()
    );
  });
});
```

(Block 7a reads `inventoryItemRepository.model.findOne` **without** `.session()` for the existing-item path — check the mock shape against block 7's usage `findOne({...})` returning a promise directly, and align: in that case make `findOne` return a thenable that also has `.session`. Follow whatever `transaction.createAtomicity.test.js` and `transaction.inventoryReversal.test.js` already do for this mock.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest tests/unit/services/transaction.newInventoryItem.test.js --silent`
Expected: FAIL — `newInventoryItem` silently ignored, no item created.

- [ ] **Step 3: Implement**

3a. In `services/transaction.service.js`, change the side-effect invocation in `persist` (line 807):

```js
      for (const sideEffect of deferredSideEffects) {
        await sideEffect(txnSession, tx);
      }
```

3b. Insert block 7a-2 after block 7a (after line 738):

```js
    // 7a-2. Consented NEW inventory item — create-or-link inside the persist
    // session (ask-first happened in the clarification loop; nothing here is
    // silent). Link-instead-of-create by exact name makes a client retry
    // idempotent: it can never mint a duplicate item. The item starts at zero
    // stock/cost and applyPurchaseStock sets both, so weighted-average cost is
    // exact. The JE is stamped with the linkage in the SAME atomic unit.
    if (
      !data.skipInventorySync &&
      PURCHASE_TYPES_TRIGGERING_STOCK.has(entryData.transactionType) &&
      !data.inventoryItemId &&
      data.newInventoryItem && typeof data.newInventoryItem === 'object'
    ) {
      const ni = data.newInventoryItem;
      const niName = String(ni.name || '').trim();
      const niQty = Number(ni.quantity);
      if (!niName) throw new ApiError(400, 'The new inventory item needs a name');
      if (!Number.isFinite(niQty) || niQty <= 0) {
        throw new ApiError(400, 'The new inventory item needs a quantity greater than zero');
      }
      const niUnit = String(ni.unit || 'units').trim() || 'units';
      const niCost = Number(ni.unitCostPrice) > 0
        ? Math.round(Number(ni.unitCostPrice) * 100) / 100
        : Math.round((entryData.amount / niQty) * 100) / 100;
      const inventoryService = require('./inventory.service');
      const escaped = niName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

      deferredSideEffects.push(async (s, savedEntry) => {
        let item = await inventoryItemRepository.model
          .findOne({ businessId: data.businessId, name: new RegExp(`^${escaped}$`, 'i') })
          .session(s);
        if (!item) {
          [item] = await inventoryItemRepository.model.create(
            [{ businessId: data.businessId, name: niName, unit: niUnit, unitCostPrice: 0, currentStock: 0 }],
            { session: s }
          );
          logger.info(`[createTransaction] auto-created inventory item "${niName}" (${item._id}) with user consent`);
        }
        await inventoryService.applyPurchaseStock(data.businessId, item._id, niQty, niCost, { userId, session: s });
        if (savedEntry?._id) {
          const JournalEntry = require('../models/JournalEntry.model');
          await JournalEntry.updateOne(
            { _id: savedEntry._id },
            { $set: { inventoryItemId: item._id, inventoryQty: niQty } },
            { session: s }
          );
        }
        data.inventoryItemId = item._id; // TRANSACTION_CREATED event carries the linkage
        data.inventoryQty = niQty;
      });
      delete data.newInventoryItem;
    }
```

- [ ] **Step 4: Run tests**

Run: `npx jest tests/unit/services/transaction.newInventoryItem.test.js tests/unit/services/transaction.createAtomicity.test.js tests/unit/services/transaction.inventoryReversal.test.js tests/unit/services/transaction.service.test.js --silent`
Expected: ALL PASS (the extra `tx` argument is invisible to existing single-arg side effects).

- [ ] **Step 5: Run the FULL backend suite + drift check**

Run: `npx jest --silent` then `node scripts/ledgerDrift.js`
Expected: all suites green; drift report 0 on every account.

- [ ] **Step 6: Commit**

```bash
git add services/transaction.service.js tests/unit/services/transaction.newInventoryItem.test.js
git commit -m "feat(ledger): consented inventory-item creation inside the atomic persist session"
```

---

### Task 12: Frontend — NL form mapping + plain-language summary utils

**Files (all in `vousfin-frontend-main/`):**
- Create: `src/utils/nlFormMapping.js` (move `nlResultToFormValues` out of the modal + add inventory mapping)
- Create: `src/utils/plainSummary.js`
- Test: `src/utils/nlFormMapping.test.js`, `src/utils/plainSummary.test.js`

**Interfaces:**
- Produces:
  - `nlResultToFormValues(result, rawText)` — exactly today's mapping (copy the body from `TransactionFormModal.jsx:654-687` verbatim) **plus** `_inventory: result.inventory || { mode: 'none' }` and `_lineItems: result.lineItems || []`.
  - `buildPlainSummary({ transactionType, amount, currency, paymentMethod, inventory })` → plain-English sentence string or `null` (Task 13 renders it). `inventory` is the preview block.

- [ ] **Step 1: Write the failing tests**

```js
// src/utils/plainSummary.test.js
import { describe, it, expect } from 'vitest'
import { buildPlainSummary } from './plainSummary'

describe('buildPlainSummary', () => {
  it('describes a stock purchase with quantity and stock movement', () => {
    const s = buildPlainSummary({
      transactionType: 'Inventory Purchase', amount: 5000, currency: 'PKR', paymentMethod: 'cash',
      inventory: { mode: 'existing', itemName: 'Rice (bag)', quantity: 10, unit: 'bags', currentStock: 12 },
    })
    expect(s).toContain('10 bags')
    expect(s).toContain('Rice (bag)')
    expect(s).toContain('Stock will go up by 10')
  })

  it('describes a new-item purchase', () => {
    const s = buildPlainSummary({
      transactionType: 'Inventory Purchase', amount: 5000, currency: 'PKR', paymentMethod: 'cash',
      inventory: { mode: 'create', itemName: 'Flour', quantity: 20, unit: 'bags' },
    })
    expect(s).toContain('Flour')
    expect(s).toContain('new item')
  })

  it('describes a stock sale with remaining stock', () => {
    const s = buildPlainSummary({
      transactionType: 'Inventory Sale', amount: 4000, currency: 'PKR', paymentMethod: 'cash',
      inventory: { mode: 'existing', itemName: 'Rice (bag)', quantity: 5, unit: 'bags', currentStock: 12 },
    })
    expect(s).toContain('Stock will go down by 5')
    expect(s).toContain('12 in stock')
  })

  it('plain expense → simple sentence, no stock talk', () => {
    const s = buildPlainSummary({
      transactionType: 'Expense', amount: 5000, currency: 'PKR', paymentMethod: 'bank',
      inventory: { mode: 'none' },
    })
    expect(s).toContain('5,000')
    expect(s).not.toMatch(/stock/i)
  })

  it('returns null without an amount', () => {
    expect(buildPlainSummary({ transactionType: 'Expense', amount: 0, inventory: { mode: 'none' } })).toBeNull()
  })
})
```

```js
// src/utils/nlFormMapping.test.js
import { describe, it, expect } from 'vitest'
import { nlResultToFormValues } from './nlFormMapping'

describe('nlResultToFormValues — inventory passthrough', () => {
  it('carries the inventory block and line items', () => {
    const v = nlResultToFormValues({
      amount: 5000, transactionType: 'Inventory Purchase',
      inventory: { mode: 'existing', itemId: 'i1', quantity: 10 },
      lineItems: [{ name: 'rice', quantity: 10 }],
    }, 'bought rice')
    expect(v._inventory).toEqual({ mode: 'existing', itemId: 'i1', quantity: 10 })
    expect(v._lineItems).toHaveLength(1)
    expect(v.amount).toBe(5000)
  })

  it('defaults to mode none when the parser sent nothing', () => {
    const v = nlResultToFormValues({ amount: 100 }, 'x')
    expect(v._inventory).toEqual({ mode: 'none' })
    expect(v._lineItems).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/utils/plainSummary.test.js src/utils/nlFormMapping.test.js`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement**

```js
// src/utils/plainSummary.js
// One plain-English sentence a non-accountant reads ABOVE the DR/CR preview.
// Pure function, no API calls. Product rule: no accounting jargon here.
import { formatCurrency } from '@/utils/formatters'

const PAY_LABEL = {
  cash: 'in cash', bank: 'by bank transfer', mobile_wallet: 'by mobile wallet',
  online: 'online', credit_card: 'by card',
}
const BUY_TYPES  = new Set(['Inventory Purchase', 'Cash Purchase', 'Credit Purchase', 'Expense', 'Asset Purchase'])
const SELL_TYPES = new Set(['Inventory Sale', 'Cash Sale', 'Credit Sale', 'Income'])

export function buildPlainSummary({ transactionType, amount, currency, paymentMethod, inventory } = {}) {
  if (!(amount > 0)) return null
  const money = formatCurrency(amount, currency)
  const paid = PAY_LABEL[paymentMethod] || ''
  const inv = inventory || { mode: 'none' }
  const qtyPhrase = inv.quantity ? `${inv.quantity} ${inv.unit || 'units'}` : ''

  if (BUY_TYPES.has(transactionType) && inv.mode === 'existing' && inv.itemName) {
    let s = `You bought ${qtyPhrase ? qtyPhrase + ' of ' : ''}${inv.itemName} for ${money}${paid ? ', paid ' + paid : ''}.`
    if (inv.quantity) s += ` Stock will go up by ${inv.quantity}.`
    return s
  }
  if (BUY_TYPES.has(transactionType) && inv.mode === 'create' && inv.itemName) {
    return `You bought ${qtyPhrase ? qtyPhrase + ' of ' : ''}${inv.itemName} for ${money}${paid ? ', paid ' + paid : ''}. ` +
      `${inv.itemName} will be added to your inventory as a new item.`
  }
  if (SELL_TYPES.has(transactionType) && inv.mode === 'existing' && inv.itemName) {
    let s = `You sold ${qtyPhrase ? qtyPhrase + ' of ' : ''}${inv.itemName} for ${money}${paid ? ', received ' + paid : ''}.`
    if (inv.quantity) s += ` Stock will go down by ${inv.quantity}.`
    if (inv.currentStock != null) s += ` You have ${inv.currentStock} in stock right now.`
    return s
  }
  if (BUY_TYPES.has(transactionType))  return `You paid ${money}${paid ? ' ' + paid : ''}.`
  if (SELL_TYPES.has(transactionType)) return `You received ${money}${paid ? ' ' + paid : ''}.`
  return null
}
```

`src/utils/nlFormMapping.js`: copy the entire `nlResultToFormValues` function body from `TransactionFormModal.jsx` lines 654-687 unchanged, converted to an ES export, and add two lines to the returned object:

```js
    _inventory:              result.inventory              || { mode: 'none' },
    _lineItems:              result.lineItems              || [],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/utils/plainSummary.test.js src/utils/nlFormMapping.test.js`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/utils/plainSummary.js src/utils/nlFormMapping.js src/utils/plainSummary.test.js src/utils/nlFormMapping.test.js
git commit -m "feat(entry): NL form mapping carries inventory block + plain-language summary util"
```

---

### Task 13: Frontend — wire inventory into the transaction modal

**Files (all in `vousfin-frontend-main/`):**
- Modify: `src/components/forms/TransactionFormModal.jsx`
  - delete local `nlResultToFormValues` (lines 654-687), import from `@/utils/nlFormMapping`
  - `StructuredFormTab`: consume `initialValues._inventory`; add `pendingNewItem` state + card; move the inventory selector up; render `buildPlainSummary`; submit `newInventoryItem`

**Interfaces:**
- Consumes: `nlResultToFormValues`, `buildPlainSummary` (Task 12); backend `newInventoryItem` (Task 10/11 — the structured form posts via `createTx` → `POST /transactions` whose controller spreads `req.body`, so `newInventoryItem` flows to `createTransaction` with **no backend change**).
- Produces: create-payload may include `newInventoryItem: { name, unit, quantity, unitCostPrice }`.

- [ ] **Step 1: Manual-verification checklist first (this task is UI wiring; automated coverage came from Task 12's pure functions).** Write down the four flows to verify at the end: (a) NL parse of a matched item prefills item+qty; (b) NL parse with consented new item shows the editable "New item" card; (c) saving the card sends `newInventoryItem`; (d) plain summary sentence renders above the DR/CR preview.

- [ ] **Step 2: Implement**

2a. Replace the local `nlResultToFormValues` (lines 654-687) with `import { nlResultToFormValues } from '@/utils/nlFormMapping'` and add `import { buildPlainSummary } from '@/utils/plainSummary'`.

2b. In `StructuredFormTab`, next to the existing inventory state (line 1013-1015), add:

```jsx
  // Smart entry — a consented brand-new item arriving from the NL parse.
  // Editable card; created atomically with the transaction at save time.
  const [pendingNewItem, setPendingNewItem] = useState(null) // { name, unit, quantity, unitCostPrice }
```

2c. In the effect that applies `initialValues` (the existing `useEffect` that resets the form when `initialValues` change — find it by searching `initialValues` inside `StructuredFormTab`), append:

```jsx
    const inv = initialValues?._inventory
    if (inv?.mode === 'existing' && inv.itemId) {
      setSelectedInventoryItemId(inv.itemId)
      setInventoryQty(inv.quantity > 0 ? inv.quantity : 1)
      setPendingNewItem(null)
    } else if (inv?.mode === 'create' && inv.itemName) {
      setSelectedInventoryItemId(null)
      setPendingNewItem({
        name: inv.itemName,
        unit: inv.unit || 'units',
        quantity: inv.quantity > 0 ? inv.quantity : 1,
        unitCostPrice: inv.unitCostPrice || null,
      })
    }
```

2d. Move the whole inventory selector block (lines 1634-1760, the `{(['Inventory Sale', ...].includes(transactionType)) && ...}` JSX) from its current position to directly AFTER the amount/date row (find the row rendering the `amount` Input and place the block after its closing tag). Drop the `inventoryItems.length > 0` requirement from the condition so the section shows even before any item exists (the new-item card is the zero-item path):

```jsx
{(['Inventory Sale', 'Inventory Purchase', 'Cash Sale', 'Credit Sale', 'Cash Purchase', 'Credit Purchase', 'Income'].includes(transactionType)) && (
```

2e. Inside that section, render the pending-item card when set (before the existing Select):

```jsx
{pendingNewItem && (
  <div className="rounded-lg border border-cyan/25 bg-cyan/5 px-4 py-3 space-y-2">
    <div className="flex items-center justify-between">
      <span className="text-[12px] font-bold text-cyan uppercase tracking-wider">New item — will be added to your inventory</span>
      <button type="button" className="text-text-muted hover:text-text-primary" aria-label="Remove new item"
        onClick={() => setPendingNewItem(null)}>
        <X className="h-4 w-4" />
      </button>
    </div>
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      <Input label="Item name" value={pendingNewItem.name}
        onChange={e => setPendingNewItem(p => ({ ...p, name: e.target.value }))} />
      <Input label="Quantity" type="number" min="0.01" step="any" value={pendingNewItem.quantity}
        onChange={e => setPendingNewItem(p => ({ ...p, quantity: parseFloat(e.target.value) || 0 }))} />
      <Input label="Unit (e.g. bags)" value={pendingNewItem.unit}
        onChange={e => setPendingNewItem(p => ({ ...p, unit: e.target.value }))} />
      <Input label="Cost per unit" type="number" min="0" step="any" value={pendingNewItem.unitCostPrice ?? ''}
        placeholder="auto from amount"
        onChange={e => setPendingNewItem(p => ({ ...p, unitCostPrice: parseFloat(e.target.value) || null }))} />
    </div>
    <p className="text-[12px] text-text-muted">
      Saving this transaction also adds “{pendingNewItem.name || 'this item'}” to your inventory with the stock above.
    </p>
  </div>
)}
```

2f. In the create-mode submit (`extras` block, line 1330-1348), after the `inventoryItemId` lines:

```jsx
      if (!selectedInventoryItemId && pendingNewItem?.name?.trim() && pendingNewItem.quantity > 0) {
        extras.newInventoryItem = {
          name: pendingNewItem.name.trim(),
          unit: pendingNewItem.unit?.trim() || 'units',
          quantity: pendingNewItem.quantity,
          unitCostPrice: pendingNewItem.unitCostPrice || null,
        }
      }
```

2g. Render the plain summary directly above the `LiveJournalPreview` usage (search for `<LiveJournalPreview` in `StructuredFormTab`):

```jsx
{(() => {
  const item = inventoryItems.find(i => i._id === selectedInventoryItemId)
  const inv = pendingNewItem
    ? { mode: 'create', itemName: pendingNewItem.name, quantity: pendingNewItem.quantity, unit: pendingNewItem.unit }
    : item
      ? { mode: 'existing', itemName: item.name, quantity: inventoryQty, unit: item.unit, currentStock: item.currentStock }
      : { mode: 'none' }
  const sentence = buildPlainSummary({
    transactionType, amount: watch('amount'), currency,
    paymentMethod: watch('paymentMethod'), inventory: inv,
  })
  return sentence ? (
    <p className="text-sm text-text-secondary rounded-lg border border-glass bg-glass-panel px-4 py-3" role="note">
      {sentence}
    </p>
  ) : null
})()}
```

2h. Clear `pendingNewItem` in the same place the form resets after success / on modal close (search for the reset that clears `setSelectedInventoryItemId(null)` at line 1165 and add `setPendingNewItem(null)`).

- [ ] **Step 3: Run the frontend test suite + lint + dev-server verification**

Run: `npx vitest run --reporter=json --outputFile=vitest-results.json` then `npm run lint`
Expected: all tests pass, no new lint errors.
Then start the dev server (`.claude/launch.json` config) and walk the four flows from Step 1 against a dev backend; screenshot the new-item card and the plain summary.

- [ ] **Step 4: Commit**

```bash
git add src/components/forms/TransactionFormModal.jsx
git commit -m "feat(entry): NL parse prefills stock item/qty, consented new-item card, plain summary"
```

---

### Task 14: Frontend — Simple mode presets util

**Files (all in `vousfin-frontend-main/`):**
- Create: `src/utils/simpleEntryPresets.js`
- Test: `src/utils/simpleEntryPresets.test.js`

**Interfaces:**
- Produces:
  - `SIMPLE_CHIPS`: array of `{ id, label, transactionType, fields }` where `fields` ⊆ `['description','category','amount','paymentMethod','date','inventory','counterparty','fromAccount','toAccount']`
  - `resolvePaymentAccount(accounts, method)` → account object or null (`cash` → code `1020` fallback `/cash/i`; `bank`/anything else → code `1010` fallback `/bank/i`)
  - `resolveChipAccounts(chip, { accounts, paymentMethod, categoryAccountId })` → `{ debitAccountId, creditAccountId }` (either may be `''` when unresolvable — the form's own validation then requires the user to pick)

Chip table (labels are user-facing — plain language, no jargon):

| id | label | transactionType | fields |
|---|---|---|---|
| `paid` | I paid for something | `Expense` | description, category, amount, paymentMethod, date |
| `gotPaid` | I got paid | `Income` | description, category, amount, paymentMethod, date |
| `boughtStock` | I bought stock to sell | `Inventory Purchase` | inventory, amount, paymentMethod, date, counterparty |
| `soldStock` | I sold stock | `Inventory Sale` | inventory, amount, paymentMethod, date, counterparty |
| `moved` | I moved money between accounts | `Bank Transfer` | fromAccount, toAccount, amount, date |
| `other` | Something else | `null` | — (switches to Advanced) |

Account wiring per chip: `paid` → debit = category (user-picked Expense account), credit = payment account; `gotPaid` → debit = payment account, credit = category (Revenue account); `boughtStock` → debit = the business's Inventory account (match name `/^inventory$/i`, fallback synonym code `1150`), credit = payment account; `soldStock` → debit = payment account, credit = Sales/Revenue account (code `4110` fallback `/sales/i`); `moved` → user picks both.

- [ ] **Step 1: Write the failing test**

```js
// src/utils/simpleEntryPresets.test.js
import { describe, it, expect } from 'vitest'
import { SIMPLE_CHIPS, resolvePaymentAccount, resolveChipAccounts } from './simpleEntryPresets'

const ACCOUNTS = [
  { _id: 'a-cash', accountName: 'Cash in Hand', accountCode: '1020', accountType: 'Asset' },
  { _id: 'a-bank', accountName: 'Cash at Bank', accountCode: '1010', accountType: 'Asset' },
  { _id: 'a-inv',  accountName: 'Inventory',    accountCode: '1150', accountType: 'Asset' },
  { _id: 'a-rev',  accountName: 'Sales Revenue', accountCode: '4110', accountType: 'Revenue' },
  { _id: 'a-rent', accountName: 'Rent Expense', accountCode: '6110', accountType: 'Expense' },
]

describe('SIMPLE_CHIPS', () => {
  it('has the six chips in plain language', () => {
    expect(SIMPLE_CHIPS.map(c => c.id)).toEqual(['paid', 'gotPaid', 'boughtStock', 'soldStock', 'moved', 'other'])
    expect(SIMPLE_CHIPS.find(c => c.id === 'boughtStock').transactionType).toBe('Inventory Purchase')
  })
})

describe('resolvePaymentAccount', () => {
  it('cash → 1020, bank → 1010', () => {
    expect(resolvePaymentAccount(ACCOUNTS, 'cash')._id).toBe('a-cash')
    expect(resolvePaymentAccount(ACCOUNTS, 'bank')._id).toBe('a-bank')
  })
  it('empty accounts → null', () => {
    expect(resolvePaymentAccount([], 'cash')).toBeNull()
  })
})

describe('resolveChipAccounts', () => {
  it('paid: category debits, payment credits', () => {
    const r = resolveChipAccounts(SIMPLE_CHIPS[0], { accounts: ACCOUNTS, paymentMethod: 'cash', categoryAccountId: 'a-rent' })
    expect(r).toEqual({ debitAccountId: 'a-rent', creditAccountId: 'a-cash' })
  })
  it('boughtStock: Inventory debits, payment credits', () => {
    const chip = SIMPLE_CHIPS.find(c => c.id === 'boughtStock')
    const r = resolveChipAccounts(chip, { accounts: ACCOUNTS, paymentMethod: 'bank' })
    expect(r).toEqual({ debitAccountId: 'a-inv', creditAccountId: 'a-bank' })
  })
  it('soldStock: payment debits, revenue credits', () => {
    const chip = SIMPLE_CHIPS.find(c => c.id === 'soldStock')
    const r = resolveChipAccounts(chip, { accounts: ACCOUNTS, paymentMethod: 'cash' })
    expect(r).toEqual({ debitAccountId: 'a-cash', creditAccountId: 'a-rev' })
  })
  it('unresolvable pieces come back as empty strings, never guesses', () => {
    const chip = SIMPLE_CHIPS.find(c => c.id === 'boughtStock')
    const r = resolveChipAccounts(chip, { accounts: [], paymentMethod: 'cash' })
    expect(r).toEqual({ debitAccountId: '', creditAccountId: '' })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/utils/simpleEntryPresets.test.js`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```js
// src/utils/simpleEntryPresets.js
// Simple-mode chip catalog + deterministic account wiring. Pure module —
// no API calls, fully unit-testable. Uses the SAME transactionType values as
// the advanced form so both modes hit the identical save path.

export const SIMPLE_CHIPS = [
  { id: 'paid',        label: 'I paid for something',            transactionType: 'Expense',            fields: ['description', 'category', 'amount', 'paymentMethod', 'date'] },
  { id: 'gotPaid',     label: 'I got paid',                      transactionType: 'Income',             fields: ['description', 'category', 'amount', 'paymentMethod', 'date'] },
  { id: 'boughtStock', label: 'I bought stock to sell',          transactionType: 'Inventory Purchase', fields: ['inventory', 'amount', 'paymentMethod', 'date', 'counterparty'] },
  { id: 'soldStock',   label: 'I sold stock',                    transactionType: 'Inventory Sale',     fields: ['inventory', 'amount', 'paymentMethod', 'date', 'counterparty'] },
  { id: 'moved',       label: 'I moved money between accounts',  transactionType: 'Bank Transfer',      fields: ['fromAccount', 'toAccount', 'amount', 'date'] },
  { id: 'other',       label: 'Something else',                  transactionType: null,                 fields: [] },
]

const byCode = (accounts, code) => accounts.find(a => a.accountCode === code) || null
const byName = (accounts, re)  => accounts.find(a => re.test(a.accountName)) || null

export function resolvePaymentAccount(accounts = [], method = 'cash') {
  if (!accounts.length) return null
  if (method === 'cash') return byCode(accounts, '1020') || byName(accounts, /cash/i)
  return byCode(accounts, '1010') || byName(accounts, /bank/i)
}

export function resolveChipAccounts(chip, { accounts = [], paymentMethod = 'cash', categoryAccountId = '' } = {}) {
  const pay = resolvePaymentAccount(accounts, paymentMethod)
  const payId = pay?._id || ''
  switch (chip?.id) {
    case 'paid':    return { debitAccountId: categoryAccountId || '', creditAccountId: payId }
    case 'gotPaid': return { debitAccountId: payId, creditAccountId: categoryAccountId || '' }
    case 'boughtStock': {
      const inv = byName(accounts, /^inventory$/i) || byCode(accounts, '1150')
      return { debitAccountId: inv?._id || '', creditAccountId: payId }
    }
    case 'soldStock': {
      const rev = byCode(accounts, '4110') || byName(accounts, /sales/i)
      return { debitAccountId: payId, creditAccountId: rev?._id || '' }
    }
    default: return { debitAccountId: '', creditAccountId: '' }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/utils/simpleEntryPresets.test.js`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/utils/simpleEntryPresets.js src/utils/simpleEntryPresets.test.js
git commit -m "feat(entry): simple-mode chip catalog with deterministic account wiring"
```

---

### Task 15: Frontend — Simple mode UI + Advanced toggle

**Files (all in `vousfin-frontend-main/`):**
- Create: `src/components/forms/SimpleEntrySection.jsx`
- Modify: `src/components/forms/TransactionFormModal.jsx` (`StructuredFormTab` gains the mode toggle; simple mode renders `SimpleEntrySection` which drives the SAME form state)

**Interfaces:**
- Consumes: `SIMPLE_CHIPS`, `resolveChipAccounts` (Task 14); react-hook-form `setValue`/`watch` handed down as props; `inventoryItems`, `accounts`, and the inventory state setters from `StructuredFormTab` (Task 13).
- Produces: `<SimpleEntrySection accounts inventoryItems currency form={{ register, setValue, watch, errors }} inventoryState={{ selectedInventoryItemId, setSelectedInventoryItemId, inventoryQty, setInventoryQty, pendingNewItem, setPendingNewItem }} onSwitchToAdvanced />`. Mode persisted in `localStorage['vf-entry-mode']` (`'simple' | 'advanced'`), default `'simple'`.

- [ ] **Step 1: Implement `SimpleEntrySection.jsx`**

```jsx
// src/components/forms/SimpleEntrySection.jsx
// Plain-question entry: six chips, 3-5 fields each. Composes the SAME
// react-hook-form state as the advanced form — one validation, one save path.
import { useState, useMemo } from 'react'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import { SIMPLE_CHIPS, resolveChipAccounts } from '@/utils/simpleEntryPresets'
import { cn } from '@/utils/cn'

export default function SimpleEntrySection({
  accounts, inventoryItems, form, inventoryState, onTypeChange, onSwitchToAdvanced,
}) {
  const { register, setValue, watch, errors } = form
  const {
    selectedInventoryItemId, setSelectedInventoryItemId,
    inventoryQty, setInventoryQty, pendingNewItem, setPendingNewItem,
  } = inventoryState
  const [chipId, setChipId] = useState(null)
  const [categoryAccountId, setCategoryAccountId] = useState('')
  const chip = SIMPLE_CHIPS.find(c => c.id === chipId) || null
  const paymentMethod = watch('paymentMethod') || 'cash'

  const categoryOptions = useMemo(() => {
    const type = chipId === 'gotPaid' ? 'Revenue' : 'Expense'
    return accounts
      .filter(a => a.accountType === type)
      .map(a => ({ value: a._id, label: a.accountName }))
  }, [accounts, chipId])

  const pickChip = (c) => {
    if (c.id === 'other') { onSwitchToAdvanced(); return }
    setChipId(c.id)
    onTypeChange(c.transactionType)
    const { debitAccountId, creditAccountId } = resolveChipAccounts(c, { accounts, paymentMethod, categoryAccountId })
    if (debitAccountId)  setValue('debitAccountId', debitAccountId,  { shouldValidate: true })
    if (creditAccountId) setValue('creditAccountId', creditAccountId, { shouldValidate: true })
  }

  // Re-wire accounts whenever payment method or category changes
  const rewire = (nextMethod = paymentMethod, nextCategory = categoryAccountId) => {
    if (!chip) return
    const { debitAccountId, creditAccountId } = resolveChipAccounts(chip, { accounts, paymentMethod: nextMethod, categoryAccountId: nextCategory })
    if (debitAccountId)  setValue('debitAccountId', debitAccountId,  { shouldValidate: true })
    if (creditAccountId) setValue('creditAccountId', creditAccountId, { shouldValidate: true })
  }

  const showField = (f) => chip?.fields.includes(f)

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary">What happened?</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2" role="group" aria-label="What happened?">
        {SIMPLE_CHIPS.map(c => (
          <button key={c.id} type="button" onClick={() => pickChip(c)}
            className={cn(
              'rounded-xl border px-3 py-3 text-sm font-medium text-left transition-colors',
              chipId === c.id ? 'border-cyan bg-cyan/10 text-text-primary' : 'border-glass bg-glass-panel text-text-secondary hover:border-cyan/50'
            )}>
            {c.label}
          </button>
        ))}
      </div>

      {chip && (
        <div className="space-y-3 animate-fade-in">
          {showField('description') && (
            <Input label="What was it for?" placeholder="e.g. office rent for July"
              error={errors.description?.message} {...register('description')} />
          )}
          {showField('category') && (
            <Select label={chipId === 'gotPaid' ? 'What kind of income?' : 'What kind of cost?'}
              options={[{ value: '', label: '— pick one —' }, ...categoryOptions]}
              value={categoryAccountId}
              onChange={(v) => { setCategoryAccountId(v); rewire(paymentMethod, v) }} />
          )}
          {showField('inventory') && (
            <div className="grid grid-cols-[2fr,1fr] gap-2">
              <Select label="Which item?"
                options={[
                  { value: '', label: '— pick an item —' },
                  ...inventoryItems.map(i => ({ value: i._id, label: `${i.name} (${i.currentStock} ${i.unit || 'units'} in stock)` })),
                  { value: '__new__', label: '+ New item…' },
                ]}
                value={pendingNewItem ? '__new__' : (selectedInventoryItemId || '')}
                onChange={(v) => {
                  if (v === '__new__') { setSelectedInventoryItemId(null); setPendingNewItem({ name: '', unit: 'units', quantity: 1, unitCostPrice: null }) }
                  else { setPendingNewItem(null); setSelectedInventoryItemId(v || null) }
                }} />
              <Input label="How many?" type="number" min="1"
                value={pendingNewItem ? pendingNewItem.quantity : inventoryQty}
                onChange={e => {
                  const q = Math.max(1, parseInt(e.target.value, 10) || 1)
                  if (pendingNewItem) setPendingNewItem(p => ({ ...p, quantity: q }))
                  else setInventoryQty(q)
                }} />
            </div>
          )}
          {pendingNewItem && showField('inventory') && (
            <Input label="New item name" placeholder="e.g. Rice (bag)"
              value={pendingNewItem.name}
              onChange={e => setPendingNewItem(p => ({ ...p, name: e.target.value }))} />
          )}
          <div className="grid grid-cols-2 gap-2">
            <Input label="Amount" type="number" min="0.01" step="any"
              error={errors.amount?.message} {...register('amount', { valueAsNumber: true })} />
            <Input label="Date" type="date"
              error={errors.transactionDate?.message} {...register('transactionDate')} />
          </div>
          {showField('paymentMethod') && (
            <Select label={chipId === 'gotPaid' || chipId === 'soldStock' ? 'How did you receive it?' : 'How did you pay?'}
              options={[{ value: 'cash', label: 'Cash' }, { value: 'bank', label: 'Bank' }]}
              value={paymentMethod}
              onChange={(v) => { setValue('paymentMethod', v); rewire(v, categoryAccountId) }} />
          )}
          {showField('fromAccount') && (
            <Select label="From account"
              options={accounts.filter(a => a.accountType === 'Asset').map(a => ({ value: a._id, label: a.accountName }))}
              value={watch('creditAccountId') || ''}
              onChange={(v) => setValue('creditAccountId', v, { shouldValidate: true })} />
          )}
          {showField('toAccount') && (
            <Select label="To account"
              options={accounts.filter(a => a.accountType === 'Asset').map(a => ({ value: a._id, label: a.accountName }))}
              value={watch('debitAccountId') || ''}
              onChange={(v) => setValue('debitAccountId', v, { shouldValidate: true })} />
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Wire the toggle into `StructuredFormTab`**

2a. Add state near the top of `StructuredFormTab`:

```jsx
  const [entryMode, setEntryMode] = useState(() => localStorage.getItem('vf-entry-mode') || 'simple')
  const switchMode = (m) => { setEntryMode(m); localStorage.setItem('vf-entry-mode', m) }
```

2b. Render a two-button toggle at the top of the form JSX (right after the period-lock banner), and when `entryMode === 'simple'` render `<SimpleEntrySection …/>` followed by the plain summary + LiveJournalPreview + submit button, hiding the rest of the advanced fields. When `'advanced'` (or in edit mode, or when `initialValues` came from an NL parse — NL prefill needs the full form), render everything as today:

```jsx
      {!isEditMode && !initialValues?._rawText && (
        <div className="flex gap-1 p-1 rounded-xl bg-glass-panel border border-glass">
          <button type="button" onClick={() => switchMode('simple')}
            className={cn('flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all',
              entryMode === 'simple' ? 'bg-cyan text-ink-on-accent' : 'text-text-secondary hover:text-text-primary')}>
            Simple
          </button>
          <button type="button" onClick={() => switchMode('advanced')}
            className={cn('flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all',
              entryMode === 'advanced' ? 'bg-cyan text-ink-on-accent' : 'text-text-secondary hover:text-text-primary')}>
            Advanced
          </button>
        </div>
      )}
```

Gate the advanced field sections with `const advancedVisible = isEditMode || entryMode === 'advanced' || !!initialValues?._rawText` and wrap the existing type-selector/account-selects/tax/FX/installment JSX in `{advancedVisible && ( … )}`. The submit button, plain summary, LiveJournalPreview, and pre-save warning panel stay visible in both modes. Simple mode passes `onTypeChange={(t) => setValue('transactionType', t)}` and `onSwitchToAdvanced={() => switchMode('advanced')}`.

- [ ] **Step 3: Verify**

Run: `npx vitest run --reporter=json --outputFile=vitest-results.json` and `npm run lint` and `npm run build`
Expected: tests pass, lint/build clean.
Then in the dev server: record an expense, a stock purchase with a new item, and a stock sale entirely from Simple mode; flip to Advanced and confirm state carries over; reload and confirm the mode choice stuck.

- [ ] **Step 4: Commit**

```bash
git add src/components/forms/SimpleEntrySection.jsx src/components/forms/TransactionFormModal.jsx
git commit -m "feat(entry): simple mode — six plain-language chips + advanced toggle, one save path"
```

---

### Task 16: End-to-end verification + docs

**Files:**
- Backend + frontend: no new code; full-suite runs, drift check, live-flow verification.

- [ ] **Step 1: Full backend suite**

Run from `vousfin-backend-main/`: `npx jest --silent`
Expected: every suite green.

- [ ] **Step 2: Ledger drift must read 0**

Run: `node scripts/ledgerDrift.js`
Expected: drift 0 on every account of every business. Any non-zero number is a stop-the-line failure — diagnose before proceeding (do NOT run the repair script to paper over a new bug).

- [ ] **Step 3: Full frontend suite + build**

Run from `vousfin-frontend-main/`: `npx vitest run --reporter=json --outputFile=vitest-results.json && npm run lint && npm run build`
Expected: green, clean.

- [ ] **Step 4: Live flows against the dev servers (seeded Code Hub business)**

1. NL: "bought 10 bags of rice for 5000 cash" with a matching item → form prefilled with item+qty → save → Inventory page shows +10 stock; JE balanced (DR Inventory / CR Cash).
2. NL: "bought 20 bags of flour for 5000 cash" (unknown item, business tracks stock) → classification question → "Sell it again" → consent question → "Yes, add it" → save → new item exists with 20 bags @ 250.
3. NL: same text answered "Use it in the business" → lands as Expense, debit is NOT Inventory, no stock movement.
4. NL: "sold 5 bags of rice for 4000 cash" → COGS lines present, stock −5.
5. NL: "sold 500 bags of rice for 400000" → plain insufficient-stock error, nothing posted.
6. Simple mode: all six chips produce balanced entries through the same POST /transactions path.
7. Reverse the flow-2 transaction from the transactions list → stock returns to previous level.

- [ ] **Step 5: Commit any test fixture/doc fallout and push**

```bash
git add -A && git commit -m "test: smart transaction entry end-to-end verification fixtures"
```

---

## Self-Review Notes (spec → plan coverage)

- Spec §1 (extraction fields + item injection + arithmetic repair) → Tasks 4, 5.
- Spec §2 (intent resolver decision table + shared matcher) → Tasks 1, 6.
- Spec §3 (clarification questions incl. vendor + cap 3) → Tasks 3, 7.
- Spec §4 (CoA chain reuse `resolveForImport`, intent→account guarantee via reclassification + debit hints, type guardrails fail-closed, single poster) → Tasks 2, 8, 9, 10.
- Spec §5 (preview inventory block, confirm carries linkage, save-time atomic create, duplicate-name link) → Tasks 9, 10, 11.
- Spec §6 (NL prefill, item picker up, new-item card, plain sentence) → Tasks 12, 13.
- Spec §7 (simple mode chips + advanced toggle, one save path, persisted choice) → Tasks 14, 15.
- Spec §8 (sales/COGS + insufficient stock) → existing backend blocks, exercised in Tasks 8 (parse side) and 16 (live).
- Spec §9 (testing incl. drift 0) → every task + Task 16.
- Out of scope confirmed: OCR path, multi-item journals, FIFO changes, new Urdu keys.
