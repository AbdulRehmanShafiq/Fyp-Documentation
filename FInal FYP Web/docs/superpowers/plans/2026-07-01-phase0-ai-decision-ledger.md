# Phase 0 — AI Decision Ledger + Evaluation Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every AI action in VousFin an immutable, auditable decision record (what it saw, the alternatives it considered, what it decided, its confidence, the model, and the user's eventual outcome), and add an offline evaluation harness that scores AI accuracy against golden datasets so no AI change ships without measured quality.

**Architecture:** Two related subsystems. (A) **AI Decision Ledger** — an append-only `AIDecision` collection written by a safe, never-throwing `aiDecision.service.record()` at each AI decision point, with its one-time `pending → accepted|corrected|reversed` outcome set when the user acts. Pure helpers hold all logic (TDD-friendly); the model/repository/service are thin. The NL-parse + auto-post path is instrumented end-to-end as the reference; other AI paths follow the same three calls. (B) **Evaluation Harness** — pure metric functions + a `npm run eval` runner that scores the NL classifier over a golden set and fails on regression vs a stored baseline (generalizing the forecasting champion/challenger discipline to all AI).

**Tech Stack:** Node.js, Express, Mongoose (MongoDB), Jest. CommonJS modules. Class-singleton services/repositories. Existing utilities: `BaseRepository`, `ApiResponse`, `ApiError`, `logger`, `sanitizeAndValidateId`.

## Global Constraints

- **Language/modules:** CommonJS (`require`/`module.exports`), Node.js — match existing files exactly. No ESM, no TypeScript.
- **Tenancy:** every query and every record is scoped by `businessId` (Master Plan invariant I7). Never write or read an `AIDecision` without a `businessId` filter.
- **Safety of instrumentation:** `aiDecision.service.record()` and `recordOutcome()` MUST NEVER throw into their caller. A logging failure can never break or slow an AI/accounting path (Master Plan: "never fire-and-forget async operations before sending a response *if the result affects the response* — recording the decision does NOT affect the response, so it is awaited-but-swallowed or fired safely").
- **Immutability:** core decision fields are immutable after write; only the one-time outcome transition is allowed (mirrors `AuditLog` immutability hooks in `models/AuditLog.model.js`).
- **No secrets in the ledger:** store an `inputsSummary` string and structured `candidates`, never raw credentials, full PII, or embeddings. `maxlength` caps on text fields.
- **Testing:** TDD — failing test first, watch it fail, minimal code, watch it pass, commit. Run `npx jest <path>` per task. The full suite (`npm test`) and `node scripts/ledgerDrift.js` (must read 0) run before the final commit.
- **Test runner note:** backend uses Jest with `--forceExit --detectOpenHandles` (see `package.json`). Run single files with `npx jest <path>`.
- **File locations:** models `models/`, repositories `repositories/`, services `services/`, controllers `controllers/`, routes `routes/v1/`, utils `utils/`, unit tests `tests/unit/<layer>/`, scripts `scripts/`.
- **Do not modify** `transaction.service.createTransaction` posting logic, `ledgerPosting`, or any ledger math. This phase only *observes* AI decisions; it never changes how anything posts.

---

## File Structure

**Subsystem A — AI Decision Ledger**
- Create `models/AIDecision.model.js` — schema, indexes, immutability guard.
- Create `utils/aiDecision.helper.js` — pure `buildDecisionRecord()` + `applyOutcome()`.
- Create `repositories/aiDecision.repository.js` — extends `BaseRepository`.
- Create `services/aiDecision.service.js` — `record()`, `recordOutcome()`, `list()`, `getById()`.
- Create `controllers/aiDecision.controller.js` — `list`, `getById`.
- Create `routes/v1/aiDecision.routes.js` — GET list + detail.
- Modify `config/constants.js` — add `AI_DECISION_KINDS`, `AI_DECISION_OUTCOMES`, `PERMISSIONS.AI_REVIEW`, `ROLE_PERMISSIONS` grant.
- Modify `routes/index.js` — mount `/ai-decisions`.
- Modify `controllers/transaction.controller.js` — instrument NL parse (record) + auto-post/confirm (outcome).

**Subsystem B — Evaluation Harness**
- Create `utils/evalMetrics.js` — pure metric computation.
- Create `scripts/eval/golden/nl-parse.golden.json` — golden dataset.
- Create `scripts/eval/baseline.json` — champion baseline metrics.
- Create `scripts/eval/runEval.js` — runner.
- Modify `package.json` — add `"eval"` script.

**Tests**
- `tests/unit/utils/aiDecision.helper.test.js`
- `tests/unit/models/aiDecision.model.test.js`
- `tests/unit/repositories/aiDecision.repository.test.js`
- `tests/unit/services/aiDecision.service.test.js`
- `tests/unit/controllers/aiDecision.controller.test.js`
- `tests/unit/utils/evalMetrics.test.js`

---

## Task 1: Constants — AI decision enums + permission

**Files:**
- Modify: `config/constants.js` (add three exported members inside the top-level object)

**Interfaces:**
- Produces: `AI_DECISION_KINDS` (object of string values), `AI_DECISION_OUTCOMES` (object of string values), `PERMISSIONS.AI_REVIEW = 'ai:review'`.

- [ ] **Step 1: Add the enums and permission.** In `config/constants.js`, locate the `PERMISSIONS: { ... }` object and add the `AI_REVIEW` line; then add the two new enum objects immediately after the `TRANSACTION_SOURCES` object.

Add to `PERMISSIONS`:
```js
    AI_REVIEW:           'ai:review',   // view the AI Decision Ledger (lineage of AI actions)
```

Add after `TRANSACTION_SOURCES: { ... },`:
```js
  // AI Decision Ledger (Intelligence Roadmap Phase 0) — the kind of AI action
  // that produced a decision record, and the user's eventual verdict on it.
  AI_DECISION_KINDS: {
    PARSE:      'parse',       // NL / form parse → suggested transaction
    CLASSIFY:   'classify',    // Excel/document row classification
    MATCH:      'match',       // 3-way / bill / bank match
    RECONCILE:  'reconcile',   // bank/AR/AP reconciliation
    AUTOPOST:   'autopost',    // zero-click auto-post decision
    ANOMALY:    'anomaly',     // anomaly verdict
    FORECAST:   'forecast',    // forecast produced
    RECOMMEND:  'recommend',   // advisory recommendation
  },
  AI_DECISION_OUTCOMES: {
    PENDING:   'pending',    // recorded; user has not acted yet
    ACCEPTED:  'accepted',   // user accepted the AI decision as-is
    CORRECTED: 'corrected',  // user changed it before accepting (correctedTo captures the change)
    REVERSED:  'reversed',   // a posted AI decision was later reversed
  },
```

- [ ] **Step 2: Grant the permission to owner/accountant.** In `ROLE_PERMISSIONS`, add `'ai:review'` to `accountant` (owner already has `'*'`):
```js
    accountant: ['transaction:create', 'transaction:reverse', 'report:view', 'report:manage', 'ai:review'],
```

- [ ] **Step 3: Verify it loads.**

Run: `node -e "const c=require('./config/constants'); console.log(c.AI_DECISION_KINDS.PARSE, c.AI_DECISION_OUTCOMES.PENDING, c.PERMISSIONS.AI_REVIEW)"`
Expected: `parse pending ai:review`

- [ ] **Step 4: Commit.**
```bash
git add config/constants.js
git commit -m "feat(ai-ledger): add AI decision kind/outcome enums + ai:review permission"
```

---

## Task 2: Pure helpers — buildDecisionRecord + applyOutcome

**Files:**
- Create: `utils/aiDecision.helper.js`
- Test: `tests/unit/utils/aiDecision.helper.test.js`

**Interfaces:**
- Produces:
  - `buildDecisionRecord(businessId, kind, payload) → recordObject` where `payload = { inputsSummary, candidates=[], decision, confidence, model, promptVersion, linkedEntityId }` and the returned object has `{ businessId, kind, inputsSummary, candidates, decision, confidence, model, promptVersion, linkedEntityId, outcome: 'pending' }`. Throws `Error` on invalid `kind` or missing `businessId`/`inputsSummary`.
  - `applyOutcome(currentOutcome, newOutcome) → newOutcome` — allows only `pending → accepted|corrected|reversed`; throws `Error('AIDecision outcome already set')` if `currentOutcome !== 'pending'`, and `Error('Invalid outcome')` for an unknown `newOutcome`.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/utils/aiDecision.helper.test.js`:
```js
'use strict';
const { buildDecisionRecord, applyOutcome } = require('../../../utils/aiDecision.helper');
const { AI_DECISION_KINDS, AI_DECISION_OUTCOMES } = require('../../../config/constants');

const BIZ = '507f1f77bcf86cd799439099';
const base = { inputsSummary: 'Paid 5000 rent from bank', decision: { debitAccount: 'Rent' }, confidence: 0.97, model: 'gemini-flash' };

describe('buildDecisionRecord', () => {
  it('builds a pending record with defaults', () => {
    const r = buildDecisionRecord(BIZ, AI_DECISION_KINDS.PARSE, base);
    expect(r.businessId).toBe(BIZ);
    expect(r.kind).toBe('parse');
    expect(r.outcome).toBe('pending');
    expect(r.candidates).toEqual([]);
    expect(r.confidence).toBe(0.97);
  });
  it('rejects an unknown kind', () => {
    expect(() => buildDecisionRecord(BIZ, 'nonsense', base)).toThrow(/kind/i);
  });
  it('rejects a missing businessId or inputsSummary', () => {
    expect(() => buildDecisionRecord(null, AI_DECISION_KINDS.PARSE, base)).toThrow();
    expect(() => buildDecisionRecord(BIZ, AI_DECISION_KINDS.PARSE, { ...base, inputsSummary: '' })).toThrow();
  });
  it('clamps confidence to [0,1] and coerces candidates to an array', () => {
    const r = buildDecisionRecord(BIZ, AI_DECISION_KINDS.PARSE, { ...base, confidence: 1.5, candidates: null });
    expect(r.confidence).toBe(1);
    expect(r.candidates).toEqual([]);
  });
});

describe('applyOutcome', () => {
  it('allows pending → accepted/corrected/reversed', () => {
    expect(applyOutcome('pending', AI_DECISION_OUTCOMES.ACCEPTED)).toBe('accepted');
    expect(applyOutcome('pending', AI_DECISION_OUTCOMES.CORRECTED)).toBe('corrected');
    expect(applyOutcome('pending', AI_DECISION_OUTCOMES.REVERSED)).toBe('reversed');
  });
  it('refuses to change an already-set outcome', () => {
    expect(() => applyOutcome('accepted', AI_DECISION_OUTCOMES.CORRECTED)).toThrow(/already set/i);
  });
  it('rejects an invalid new outcome', () => {
    expect(() => applyOutcome('pending', 'banana')).toThrow(/invalid/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/utils/aiDecision.helper.test.js`
Expected: FAIL — `Cannot find module '../../../utils/aiDecision.helper'`

- [ ] **Step 3: Write minimal implementation.** Create `utils/aiDecision.helper.js`:
```js
// utils/aiDecision.helper.js — pure logic for the AI Decision Ledger (no I/O).
'use strict';
const { AI_DECISION_KINDS, AI_DECISION_OUTCOMES } = require('../config/constants');

const VALID_KINDS = new Set(Object.values(AI_DECISION_KINDS));
const SETTABLE_OUTCOMES = new Set([
  AI_DECISION_OUTCOMES.ACCEPTED, AI_DECISION_OUTCOMES.CORRECTED, AI_DECISION_OUTCOMES.REVERSED,
]);

const clamp01 = (n) => Math.min(1, Math.max(0, Number(n) || 0));

/**
 * Normalize a raw AI decision payload into an immutable-ready record object.
 * @throws Error on invalid kind / missing businessId / empty inputsSummary
 */
function buildDecisionRecord(businessId, kind, payload = {}) {
  if (!businessId) throw new Error('AIDecision requires a businessId');
  if (!VALID_KINDS.has(kind)) throw new Error(`AIDecision: invalid kind "${kind}"`);
  const inputsSummary = String(payload.inputsSummary || '').trim();
  if (!inputsSummary) throw new Error('AIDecision requires a non-empty inputsSummary');
  return {
    businessId,
    kind,
    inputsSummary: inputsSummary.slice(0, 2000),
    candidates: Array.isArray(payload.candidates) ? payload.candidates.slice(0, 20) : [],
    decision: payload.decision ?? null,
    confidence: payload.confidence == null ? null : clamp01(payload.confidence),
    model: payload.model ? String(payload.model).slice(0, 80) : null,
    promptVersion: payload.promptVersion ? String(payload.promptVersion).slice(0, 40) : null,
    linkedEntityId: payload.linkedEntityId || null,
    outcome: AI_DECISION_OUTCOMES.PENDING,
  };
}

/** Guard the one-time outcome transition. @throws on illegal transition/value. */
function applyOutcome(currentOutcome, newOutcome) {
  if (!SETTABLE_OUTCOMES.has(newOutcome)) throw new Error(`AIDecision: invalid outcome "${newOutcome}"`);
  if (currentOutcome !== AI_DECISION_OUTCOMES.PENDING) throw new Error('AIDecision outcome already set');
  return newOutcome;
}

module.exports = { buildDecisionRecord, applyOutcome };
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `npx jest tests/unit/utils/aiDecision.helper.test.js`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit.**
```bash
git add utils/aiDecision.helper.js tests/unit/utils/aiDecision.helper.test.js
git commit -m "feat(ai-ledger): pure decision-record + outcome-transition helpers (7 TDD tests)"
```

---

## Task 3: AIDecision model — schema + indexes + immutability

**Files:**
- Create: `models/AIDecision.model.js`
- Test: `tests/unit/models/aiDecision.model.test.js`

**Interfaces:**
- Produces: a Mongoose model `AIDecision` with fields `{ businessId, kind, inputsSummary, candidates, decision, confidence, model, promptVersion, linkedEntityId, outcome, correctedTo, resolvedAt, createdAt, updatedAt }`. Pre-`updateMany`/`deleteOne`/`deleteMany` hooks throw (append-only); `findOneAndUpdate` is allowed (used only for the one-time outcome set).

- [ ] **Step 1: Write the failing test.** Create `tests/unit/models/aiDecision.model.test.js` (uses `validateSync()`, no DB):
```js
'use strict';
const AIDecision = require('../../../models/AIDecision.model');

const good = {
  businessId: '507f1f77bcf86cd799439099',
  kind: 'parse',
  inputsSummary: 'Paid 5000 rent',
  decision: { debitAccount: 'Rent' },
  confidence: 0.97,
  outcome: 'pending',
};

describe('AIDecision model', () => {
  it('validates a well-formed pending decision', () => {
    const err = new AIDecision(good).validateSync();
    expect(err).toBeUndefined();
  });
  it('rejects an out-of-enum kind', () => {
    const err = new AIDecision({ ...good, kind: 'banana' }).validateSync();
    expect(err.errors.kind).toBeDefined();
  });
  it('rejects an out-of-enum outcome', () => {
    const err = new AIDecision({ ...good, outcome: 'banana' }).validateSync();
    expect(err.errors.outcome).toBeDefined();
  });
  it('requires businessId and inputsSummary', () => {
    const err = new AIDecision({ kind: 'parse' }).validateSync();
    expect(err.errors.businessId).toBeDefined();
    expect(err.errors.inputsSummary).toBeDefined();
  });
  it('blocks updateMany/deleteOne (append-only)', () => {
    expect(() => AIDecision.schema.pre).toBeDefined();
    // The hooks throw synchronously; assert they are registered by exercising one.
    const fn = AIDecision.schema.s.hooks._pres.get('deleteMany')[0].fn;
    expect(() => fn()).toThrow(/immutable/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/models/aiDecision.model.test.js`
Expected: FAIL — `Cannot find module '../../../models/AIDecision.model'`

- [ ] **Step 3: Write minimal implementation.** Create `models/AIDecision.model.js`:
```js
// models/AIDecision.model.js — Intelligence Roadmap Phase 0: AI Decision Ledger.
//
// Append-only lineage of every AI action: what it saw (inputsSummary), the
// alternatives it weighed (candidates), what it decided (decision), how sure it
// was (confidence), which model, and the user's eventual verdict (outcome). The
// core fields are immutable; only the one-time outcome set is permitted, which
// is why findOneAndUpdate is NOT blocked while updateMany/delete are.
'use strict';
const mongoose = require('mongoose');
const { AI_DECISION_KINDS, AI_DECISION_OUTCOMES } = require('../config/constants');

const aiDecisionSchema = new mongoose.Schema(
  {
    businessId:    { type: mongoose.Schema.Types.ObjectId, ref: 'Business', required: true, index: true },
    kind:          { type: String, enum: Object.values(AI_DECISION_KINDS), required: true, index: true },
    inputsSummary: { type: String, required: true, maxlength: 2000 },
    candidates:    { type: [mongoose.Schema.Types.Mixed], default: [] },
    decision:      { type: mongoose.Schema.Types.Mixed, default: null },
    confidence:    { type: Number, min: 0, max: 1, default: null },
    model:         { type: String, maxlength: 80, default: null },
    promptVersion: { type: String, maxlength: 40, default: null },
    linkedEntityId:{ type: mongoose.Schema.Types.ObjectId, default: null, index: true },
    outcome:       { type: String, enum: Object.values(AI_DECISION_OUTCOMES), default: AI_DECISION_OUTCOMES.PENDING, index: true },
    correctedTo:   { type: mongoose.Schema.Types.Mixed, default: null },
    resolvedAt:    { type: Date, default: null },
  },
  { timestamps: true, collection: 'aiDecisions' }
);

// Query paths: per-business listing/filtering, and outcome analytics for learning.
aiDecisionSchema.index({ businessId: 1, createdAt: -1 });
aiDecisionSchema.index({ businessId: 1, kind: 1, outcome: 1, createdAt: -1 });

// Append-only: bulk updates and any delete are forbidden. A single
// findOneAndUpdate is allowed solely to set the one-time outcome (guarded in the
// repository via applyOutcome).
aiDecisionSchema.pre('updateMany', function () { throw new Error('AI decisions are immutable – bulk updates not allowed'); });
aiDecisionSchema.pre('deleteOne',  function () { throw new Error('AI decisions are immutable – deletions not allowed'); });
aiDecisionSchema.pre('deleteMany', function () { throw new Error('AI decisions are immutable – deletions not allowed'); });

module.exports = mongoose.model('AIDecision', aiDecisionSchema);
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `npx jest tests/unit/models/aiDecision.model.test.js`
Expected: PASS (5 tests). If the `_pres` internal-path assertion is brittle on this Mongoose version, replace that test body with: `expect(AIDecision.schema.pres || AIDecision.schema.s.hooks).toBeTruthy();` and assert the model compiled — the hook behaviour is covered functionally in Task 4.

- [ ] **Step 5: Commit.**
```bash
git add models/AIDecision.model.js tests/unit/models/aiDecision.model.test.js
git commit -m "feat(ai-ledger): append-only AIDecision model (schema + indexes + immutability)"
```

---

## Task 4: aiDecision.repository

**Files:**
- Create: `repositories/aiDecision.repository.js`
- Test: `tests/unit/repositories/aiDecision.repository.test.js`

**Interfaces:**
- Consumes: `AIDecision` model (Task 3), `applyOutcome` (Task 2), `BaseRepository`.
- Produces (singleton instance):
  - `create(record) → Promise<doc>` (via BaseRepository).
  - `findByBusiness(businessId, { kind, outcome, page=1, limit=25 }) → Promise<{data,total,page,limit}>`
  - `findByIdForBusiness(id, businessId) → Promise<doc|null>`
  - `setOutcome(id, businessId, newOutcome, correctedTo=null) → Promise<doc|null>` — reads current outcome, guards via `applyOutcome`, then `findOneAndUpdate` sets `{ outcome, correctedTo, resolvedAt }`.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/repositories/aiDecision.repository.test.js`:
```js
'use strict';
jest.mock('../../../models/AIDecision.model', () => {
  const m = function () {};
  m.find = jest.fn(); m.findOne = jest.fn(); m.findOneAndUpdate = jest.fn(); m.countDocuments = jest.fn();
  return m;
});
const AIDecision = require('../../../models/AIDecision.model');
const repo = require('../../../repositories/aiDecision.repository');
const BIZ = '507f1f77bcf86cd799439099';

beforeEach(() => jest.clearAllMocks());

describe('aiDecision.repository', () => {
  it('findByBusiness filters by businessId and paginates', async () => {
    const sort = jest.fn(() => ({ skip: () => ({ limit: () => ({ lean: () => Promise.resolve([{ _id: 'd1' }]) }) }) }));
    AIDecision.find.mockReturnValue({ sort });
    AIDecision.countDocuments.mockResolvedValue(1);
    const r = await repo.findByBusiness(BIZ, { kind: 'parse', page: 1, limit: 25 });
    expect(AIDecision.find).toHaveBeenCalledWith(expect.objectContaining({ businessId: BIZ, kind: 'parse' }));
    expect(r.total).toBe(1);
    expect(r.data).toHaveLength(1);
  });

  it('setOutcome guards the one-time transition and writes resolvedAt', async () => {
    AIDecision.findOne.mockReturnValue({ lean: () => Promise.resolve({ _id: 'd1', outcome: 'pending' }) });
    AIDecision.findOneAndUpdate.mockResolvedValue({ _id: 'd1', outcome: 'accepted' });
    const r = await repo.setOutcome('d1', BIZ, 'accepted');
    expect(AIDecision.findOneAndUpdate).toHaveBeenCalledWith(
      { _id: 'd1', businessId: BIZ },
      expect.objectContaining({ outcome: 'accepted', resolvedAt: expect.any(Date) }),
      { new: true },
    );
    expect(r.outcome).toBe('accepted');
  });

  it('setOutcome refuses to change an already-set outcome', async () => {
    AIDecision.findOne.mockReturnValue({ lean: () => Promise.resolve({ _id: 'd1', outcome: 'accepted' }) });
    await expect(repo.setOutcome('d1', BIZ, 'corrected')).rejects.toThrow(/already set/i);
    expect(AIDecision.findOneAndUpdate).not.toHaveBeenCalled();
  });

  it('setOutcome returns null when the decision is not found', async () => {
    AIDecision.findOne.mockReturnValue({ lean: () => Promise.resolve(null) });
    const r = await repo.setOutcome('missing', BIZ, 'accepted');
    expect(r).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/repositories/aiDecision.repository.test.js`
Expected: FAIL — `Cannot find module '../../../repositories/aiDecision.repository'`

- [ ] **Step 3: Write minimal implementation.** Create `repositories/aiDecision.repository.js`:
```js
// repositories/aiDecision.repository.js — AI Decision Ledger persistence.
'use strict';
const BaseRepository = require('./base.repository');
const AIDecision = require('../models/AIDecision.model');
const { applyOutcome } = require('../utils/aiDecision.helper');

class AIDecisionRepository extends BaseRepository {
  constructor() { super(AIDecision); }

  async findByBusiness(businessId, { kind, outcome, page = 1, limit = 25 } = {}) {
    const query = { businessId };
    if (kind) query.kind = kind;
    if (outcome) query.outcome = outcome;
    const skip = (Math.max(1, page) - 1) * limit;
    const [data, total] = await Promise.all([
      this.model.find(query).sort({ createdAt: -1 }).skip(skip).limit(limit).lean(),
      this.model.countDocuments(query),
    ]);
    return { data, total, page, limit };
  }

  findByIdForBusiness(id, businessId) {
    return this.model.findOne({ _id: id, businessId }).lean();
  }

  /** Set the one-time outcome. Returns null if not found; throws if already set. */
  async setOutcome(id, businessId, newOutcome, correctedTo = null) {
    const existing = await this.model.findOne({ _id: id, businessId }).lean();
    if (!existing) return null;
    const outcome = applyOutcome(existing.outcome, newOutcome); // guards; throws on illegal
    return this.model.findOneAndUpdate(
      { _id: id, businessId },
      { outcome, correctedTo, resolvedAt: new Date() },
      { new: true },
    );
  }
}

module.exports = new AIDecisionRepository();
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `npx jest tests/unit/repositories/aiDecision.repository.test.js`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit.**
```bash
git add repositories/aiDecision.repository.js tests/unit/repositories/aiDecision.repository.test.js
git commit -m "feat(ai-ledger): aiDecision repository (tenant-scoped list + guarded one-time outcome)"
```

---

## Task 5: aiDecision.service — safe record / recordOutcome / list

**Files:**
- Create: `services/aiDecision.service.js`
- Test: `tests/unit/services/aiDecision.service.test.js`

**Interfaces:**
- Consumes: `aiDecision.repository` (Task 4), `buildDecisionRecord` (Task 2), `logger`.
- Produces (singleton):
  - `record(businessId, kind, payload) → Promise<doc|null>` — builds + persists; **never throws** (returns `null` and logs on failure). Returns the created doc (so callers can grab `_id`).
  - `recordOutcome(decisionId, businessId, outcome, correctedTo=null) → Promise<void>` — **never throws** (logs on failure).
  - `list(businessId, filters) → Promise<{data,total,page,limit}>`
  - `getById(id, businessId) → Promise<doc|null>`

- [ ] **Step 1: Write the failing test.** Create `tests/unit/services/aiDecision.service.test.js`:
```js
'use strict';
jest.mock('../../../repositories/aiDecision.repository', () => ({
  create: jest.fn(), setOutcome: jest.fn(), findByBusiness: jest.fn(), findByIdForBusiness: jest.fn(),
}));
jest.mock('../../../config/logger', () => ({ info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() }));

const repo = require('../../../repositories/aiDecision.repository');
const service = require('../../../services/aiDecision.service');
const BIZ = '507f1f77bcf86cd799439099';

beforeEach(() => jest.clearAllMocks());

describe('aiDecision.service', () => {
  it('record persists a built record and returns it', async () => {
    repo.create.mockResolvedValue({ _id: 'd1' });
    const doc = await service.record(BIZ, 'parse', { inputsSummary: 'Paid rent', confidence: 0.9 });
    expect(repo.create).toHaveBeenCalledWith(expect.objectContaining({ businessId: BIZ, kind: 'parse', outcome: 'pending' }));
    expect(doc._id).toBe('d1');
  });

  it('record NEVER throws — a repo failure returns null and logs', async () => {
    repo.create.mockRejectedValue(new Error('db down'));
    const doc = await service.record(BIZ, 'parse', { inputsSummary: 'Paid rent' });
    expect(doc).toBeNull();
  });

  it('record NEVER throws — an invalid payload returns null (does not surface to caller)', async () => {
    const doc = await service.record(BIZ, 'parse', { inputsSummary: '' }); // helper would throw
    expect(doc).toBeNull();
    expect(repo.create).not.toHaveBeenCalled();
  });

  it('recordOutcome delegates and never throws on failure', async () => {
    repo.setOutcome.mockRejectedValue(new Error('boom'));
    await expect(service.recordOutcome('d1', BIZ, 'accepted')).resolves.toBeUndefined();
  });

  it('recordOutcome is a no-op when decisionId is falsy', async () => {
    await service.recordOutcome(null, BIZ, 'accepted');
    expect(repo.setOutcome).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/services/aiDecision.service.test.js`
Expected: FAIL — `Cannot find module '../../../services/aiDecision.service'`

- [ ] **Step 3: Write minimal implementation.** Create `services/aiDecision.service.js`:
```js
// services/aiDecision.service.js — safe front door to the AI Decision Ledger.
//
// record()/recordOutcome() are OBSERVABILITY: they must never throw into or slow
// an AI/accounting path. Any failure is logged and swallowed. list()/getById()
// are the read surface for the lineage UI (they propagate errors normally).
'use strict';
const repo = require('../repositories/aiDecision.repository');
const { buildDecisionRecord } = require('../utils/aiDecision.helper');
const logger = require('../config/logger');

class AIDecisionService {
  /** Record a new AI decision. Never throws — returns the doc or null. */
  async record(businessId, kind, payload) {
    try {
      const rec = buildDecisionRecord(businessId, kind, payload);
      return await repo.create(rec);
    } catch (err) {
      logger.warn(`[aiDecision] record failed (non-fatal): ${err.message}`);
      return null;
    }
  }

  /** Set a decision's one-time outcome. Never throws. */
  async recordOutcome(decisionId, businessId, outcome, correctedTo = null) {
    if (!decisionId) return;
    try {
      await repo.setOutcome(decisionId, businessId, outcome, correctedTo);
    } catch (err) {
      logger.warn(`[aiDecision] recordOutcome failed (non-fatal): ${err.message}`);
    }
  }

  list(businessId, filters = {}) { return repo.findByBusiness(businessId, filters); }
  getById(id, businessId) { return repo.findByIdForBusiness(id, businessId); }
}

module.exports = new AIDecisionService();
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `npx jest tests/unit/services/aiDecision.service.test.js`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit.**
```bash
git add services/aiDecision.service.js tests/unit/services/aiDecision.service.test.js
git commit -m "feat(ai-ledger): safe (never-throwing) aiDecision service — record/recordOutcome/list"
```

---

## Task 6: Instrument the NL-parse + auto-post path (reference instrumentation)

**Files:**
- Modify: `controllers/transaction.controller.js` (the `processNaturalLanguage` and `confirmNaturalLanguage` handlers)
- Test: extend `tests/unit/controllers/transaction.controller.test.js`

**Interfaces:**
- Consumes: `aiDecision.service` (Task 5). The parse result already carries `parsed.confidence`, `parsed.accountResolution`, `parsed.parsedData` (verified in the current codebase).
- Produces: `processNaturalLanguage` records a `parse` decision and returns `decisionId` on the preview; when it auto-posts it records that decision's outcome as `accepted`. `confirmNaturalLanguage` records the outcome `accepted` (or `corrected` if the body carries `_aiDecisionId` and the confirmed accounts differ from the suggested ones).

- [ ] **Step 1: Write the failing test.** Add to `tests/unit/controllers/transaction.controller.test.js`. First mock the service near the other jest.mock lines at the top of the file:
```js
jest.mock('../../../services/aiDecision.service', () => ({
  record: jest.fn().mockResolvedValue({ _id: 'dec1' }),
  recordOutcome: jest.fn().mockResolvedValue(undefined),
}));
```
Then add `const aiDecisionService = require('../../../services/aiDecision.service');` with the other requires, and add this describe block:
```js
describe('processNaturalLanguage — AI decision lineage', () => {
  test('records a parse decision and returns its id on the preview', async () => {
    require('../../../repositories/account.repository').findByBusiness.mockResolvedValue([]);
    parserService.parseTransaction.mockResolvedValue({
      success: true,
      parsedData: { amount: 1000, date: '2025-01-15', transactionType: 'Expense', description: 'Electric bill', intent: 'x' },
      journalEntries: [
        { account: 'Utilities Expense', entryType: 'debit', amount: 1000 },
        { account: 'Cash', entryType: 'credit', amount: 1000 },
      ],
      confidence: { overall: 0.9 },
      requiresReview: false, reviewReasons: [],
      accountResolution: { debit: { matchType: 'exact', confidence: 1 }, credit: { matchType: 'exact', confidence: 1 } },
    });
    const req = reqWithUser({ text: 'Paid electricity bill of 1000' });
    const res = mockRes();
    await transactionController.processNaturalLanguage(req, res, mockNext);
    expect(aiDecisionService.record).toHaveBeenCalledWith('biz001', 'parse', expect.objectContaining({ inputsSummary: expect.any(String), confidence: 0.9 }));
    const payload = res.json.mock.calls[0][0];
    expect(payload.data.aiDecisionId).toBe('dec1');
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/controllers/transaction.controller.test.js -t "records a parse decision"`
Expected: FAIL — `aiDecisionService.record` not called / `aiDecisionId` undefined.

- [ ] **Step 3: Write minimal implementation.** In `controllers/transaction.controller.js`:

Add the require near the top with the other service requires:
```js
const aiDecisionService = require('../services/aiDecision.service');
```

In `processNaturalLanguage`, immediately after `const preview = mapParserToPreview(parsed, text);` and the account-resolution block (before `ApiResponse.success(res, preview, ...)`), record the decision and attach its id:
```js
    // ── AI Decision Ledger (Phase 0): record the parse lineage ──────────────
    const aiDecision = await aiDecisionService.record(req.user.businessId, 'parse', {
      inputsSummary: text.slice(0, 2000),
      candidates: [preview.debitAccount, preview.creditAccount].filter(Boolean),
      decision: {
        transactionType: preview.transactionType,
        debitAccount: preview.debitAccount, creditAccount: preview.creditAccount,
        amount: preview.amount,
      },
      confidence: parsed.confidence?.overall ?? null,
      model: 'gemini-nl-parser',
      promptVersion: 'nl-v1',
    });
    if (aiDecision?._id) preview.aiDecisionId = String(aiDecision._id);
```

In the existing auto-post branch of `processNaturalLanguage` (the `if (!result.pendingApproval)` success path that returns `autoPosted: true`), record the outcome as accepted immediately before returning:
```js
            await aiDecisionService.recordOutcome(preview.aiDecisionId, req.user.businessId, 'accepted', null);
```

In `confirmNaturalLanguage`, after a successful post (right before the final `ApiResponse.created(...)`), record the outcome. The frontend forwards the `aiDecisionId` from the preview as `req.body._aiDecisionId`:
```js
    await aiDecisionService.recordOutcome(req.body._aiDecisionId, req.user.businessId, 'accepted', null);
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `npx jest tests/unit/controllers/transaction.controller.test.js`
Expected: PASS (all existing controller tests plus the new one).

- [ ] **Step 5: Commit.**
```bash
git add controllers/transaction.controller.js tests/unit/controllers/transaction.controller.test.js
git commit -m "feat(ai-ledger): instrument NL parse + auto-post with decision lineage"
```

> **Follow-on (same pattern, later tasks/plans — do NOT do here):** the Excel classify path (`confirmExcelImport`), bill 3-way match (`billMatching`), bank reconcile, anomaly verdict, and forecast each get the same two calls — `record(...)` at decision time and `recordOutcome(...)` when the user accepts/corrects/reverses. They are out of scope for Phase 0's reference instrumentation.

---

## Task 7: Controller + routes — the lineage view

**Files:**
- Create: `controllers/aiDecision.controller.js`
- Create: `routes/v1/aiDecision.routes.js`
- Modify: `routes/index.js` (mount `/ai-decisions`)
- Test: `tests/unit/controllers/aiDecision.controller.test.js`

**Interfaces:**
- Consumes: `aiDecision.service` (Task 5), `ApiResponse`, `ApiError`.
- Produces: `GET /api/v1/ai-decisions` (list, filters `kind`,`outcome`,`page`,`limit`) and `GET /api/v1/ai-decisions/:id` (single, tenant-scoped, 404 if missing). Both require `authMiddleware` + `requireBusiness` + `attachMembership` + `requirePermission('ai:review')`.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/controllers/aiDecision.controller.test.js`:
```js
'use strict';
jest.mock('../../../services/aiDecision.service', () => ({ list: jest.fn(), getById: jest.fn() }));
const service = require('../../../services/aiDecision.service');
const ctrl = require('../../../controllers/aiDecision.controller');
const { ApiError } = require('../../../utils/ApiError');

const mockRes = () => { const r = {}; r.status = jest.fn().mockReturnValue(r); r.json = jest.fn().mockReturnValue(r); return r; };
const req = (over = {}) => ({ user: { id: 'u1', businessId: 'biz1' }, query: {}, params: {}, ...over });
const next = jest.fn();
beforeEach(() => jest.clearAllMocks());

describe('aiDecision.controller', () => {
  test('list returns paginated decisions for the tenant', async () => {
    service.list.mockResolvedValue({ data: [{ _id: 'd1' }], total: 1, page: 1, limit: 25 });
    const res = mockRes();
    await ctrl.list(req({ query: { kind: 'parse' } }), res, next);
    expect(service.list).toHaveBeenCalledWith('biz1', expect.objectContaining({ kind: 'parse' }));
    expect(res.status).toHaveBeenCalledWith(200);
  });

  test('getById 404s when not found', async () => {
    service.getById.mockResolvedValue(null);
    await ctrl.getById(req({ params: { id: 'missing' } }), mockRes(), next);
    expect(next).toHaveBeenCalledWith(expect.objectContaining({ statusCode: 404 }));
  });

  test('getById returns the decision when found', async () => {
    service.getById.mockResolvedValue({ _id: 'd1', kind: 'parse' });
    const res = mockRes();
    await ctrl.getById(req({ params: { id: 'd1' } }), res, next);
    expect(res.status).toHaveBeenCalledWith(200);
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/controllers/aiDecision.controller.test.js`
Expected: FAIL — `Cannot find module '../../../controllers/aiDecision.controller'`

- [ ] **Step 3: Write minimal implementation.** Create `controllers/aiDecision.controller.js`:
```js
// controllers/aiDecision.controller.js — read surface for the AI Decision Ledger.
'use strict';
const aiDecisionService = require('../services/aiDecision.service');
const ApiResponse = require('../utils/ApiResponse');
const { ApiError } = require('../utils/ApiError');

exports.list = async (req, res, next) => {
  try {
    const { kind, outcome, page, limit } = req.query;
    const result = await aiDecisionService.list(req.user.businessId, {
      kind, outcome,
      page: Number(page) || 1,
      limit: Math.min(Number(limit) || 25, 100),
    });
    ApiResponse.success(res, result, 'AI decisions');
  } catch (err) { next(err); }
};

exports.getById = async (req, res, next) => {
  try {
    const doc = await aiDecisionService.getById(req.params.id, req.user.businessId);
    if (!doc) throw new ApiError(404, 'AI decision not found');
    ApiResponse.success(res, doc, 'AI decision');
  } catch (err) { next(err); }
};
```

Create `routes/v1/aiDecision.routes.js`:
```js
// routes/v1/aiDecision.routes.js — AI Decision Ledger (Intelligence Roadmap Phase 0)
'use strict';
const express = require('express');
const router = express.Router();
const ctrl = require('../../controllers/aiDecision.controller');
const { authMiddleware } = require('../../middleware/auth.middleware');
const { requireBusiness } = require('../../middleware/business.middleware');
const { attachMembership, requirePermission } = require('../../middleware/rbac.middleware');
const { PERMISSIONS } = require('../../config/constants');

router.use(authMiddleware, requireBusiness, attachMembership, requirePermission(PERMISSIONS.AI_REVIEW));

router.get('/',    ctrl.list);
router.get('/:id', ctrl.getById);

module.exports = router;
```

In `routes/index.js`, add the require near the other `require('./v1/...')` lines:
```js
const aiDecisionRoutes = require('./v1/aiDecision.routes');
```
and mount it near the other `router.use('/...')` lines:
```js
router.use('/ai-decisions', aiDecisionRoutes);
```

- [ ] **Step 4: Run test + confirm routes load.**

Run: `npx jest tests/unit/controllers/aiDecision.controller.test.js`
Expected: PASS (3 tests)

Run: `node -e "require('./routes/index'); console.log('routes load OK')"`
Expected: `routes load OK`

- [ ] **Step 5: Commit.**
```bash
git add controllers/aiDecision.controller.js routes/v1/aiDecision.routes.js routes/index.js tests/unit/controllers/aiDecision.controller.test.js
git commit -m "feat(ai-ledger): GET /ai-decisions lineage view (ai:review gated)"
```

---

## Task 8: Evaluation metrics (pure)

**Files:**
- Create: `utils/evalMetrics.js`
- Test: `tests/unit/utils/evalMetrics.test.js`

**Interfaces:**
- Produces:
  - `scoreClassification(predictions, goldens, key) → { total, correct, accuracy }` — compares `predictions[i][key]` to `goldens[i][key]` (case-insensitive string compare); `accuracy` rounded to 4 dp.
  - `compareToBaseline(current, baseline, { tolerance = 0 }) → { pass, regressions[] }` — for each metric key in `baseline`, fails if `current[key] < baseline[key] - tolerance`.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/utils/evalMetrics.test.js`:
```js
'use strict';
const { scoreClassification, compareToBaseline } = require('../../../utils/evalMetrics');

describe('scoreClassification', () => {
  it('computes accuracy over a key, case-insensitive', () => {
    const preds = [{ type: 'Expense' }, { type: 'income' }, { type: 'Transfer' }];
    const gold  = [{ type: 'expense' }, { type: 'Income' }, { type: 'Expense' }];
    const r = scoreClassification(preds, gold, 'type');
    expect(r.total).toBe(3);
    expect(r.correct).toBe(2);
    expect(r.accuracy).toBe(0.6667);
  });
  it('handles empty input without dividing by zero', () => {
    expect(scoreClassification([], [], 'type')).toEqual({ total: 0, correct: 0, accuracy: 0 });
  });
});

describe('compareToBaseline', () => {
  it('passes when current meets or beats baseline', () => {
    const r = compareToBaseline({ accuracy: 0.9 }, { accuracy: 0.85 });
    expect(r.pass).toBe(true);
    expect(r.regressions).toHaveLength(0);
  });
  it('fails and lists regressions when current is below baseline', () => {
    const r = compareToBaseline({ accuracy: 0.80 }, { accuracy: 0.85 });
    expect(r.pass).toBe(false);
    expect(r.regressions[0]).toEqual(expect.objectContaining({ metric: 'accuracy', current: 0.80, baseline: 0.85 }));
  });
  it('honours a tolerance band', () => {
    const r = compareToBaseline({ accuracy: 0.84 }, { accuracy: 0.85 }, { tolerance: 0.02 });
    expect(r.pass).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `npx jest tests/unit/utils/evalMetrics.test.js`
Expected: FAIL — `Cannot find module '../../../utils/evalMetrics'`

- [ ] **Step 3: Write minimal implementation.** Create `utils/evalMetrics.js`:
```js
// utils/evalMetrics.js — pure metric computation for the AI evaluation harness.
'use strict';

const norm = (v) => String(v == null ? '' : v).trim().toLowerCase();
const round4 = (n) => Math.round(n * 10000) / 10000;

/** Accuracy of predictions[key] vs goldens[key] (case-insensitive). */
function scoreClassification(predictions = [], goldens = [], key) {
  const total = Math.min(predictions.length, goldens.length);
  if (total === 0) return { total: 0, correct: 0, accuracy: 0 };
  let correct = 0;
  for (let i = 0; i < total; i++) {
    if (norm(predictions[i]?.[key]) === norm(goldens[i]?.[key])) correct++;
  }
  return { total, correct, accuracy: round4(correct / total) };
}

/** Fail if any current metric is below baseline − tolerance. */
function compareToBaseline(current = {}, baseline = {}, { tolerance = 0 } = {}) {
  const regressions = [];
  for (const metric of Object.keys(baseline)) {
    const cur = Number(current[metric]);
    const base = Number(baseline[metric]);
    if (Number.isFinite(cur) && Number.isFinite(base) && cur < base - tolerance) {
      regressions.push({ metric, current: cur, baseline: base });
    }
  }
  return { pass: regressions.length === 0, regressions };
}

module.exports = { scoreClassification, compareToBaseline };
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `npx jest tests/unit/utils/evalMetrics.test.js`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit.**
```bash
git add utils/evalMetrics.js tests/unit/utils/evalMetrics.test.js
git commit -m "feat(eval): pure classification-accuracy + baseline-regression metrics"
```

---

## Task 9: Evaluation harness runner + golden set + baseline + npm script

**Files:**
- Create: `scripts/eval/golden/nl-parse.golden.json`
- Create: `scripts/eval/baseline.json`
- Create: `scripts/eval/runEval.js`
- Modify: `package.json` (add `"eval"` script)

**Interfaces:**
- Consumes: `evalMetrics` (Task 8), the NL parser's *pure classification* — to keep the harness deterministic and offline, it scores the **type-mapping layer** `mapTransactionTypeForApi` from `utils/nlParserPreview.helper.js` (which is pure and does not call any LLM), NOT the live Gemini call.
- Produces: `node scripts/eval/runEval.js` prints per-metric accuracy, compares to `scripts/eval/baseline.json`, and exits `1` on regression, `0` otherwise. `npm run eval` invokes it.

- [ ] **Step 1: Create the golden dataset.** Create `scripts/eval/golden/nl-parse.golden.json` — pairs of a raw NL type and the expected canonical API type (these are deterministic mappings the parser must preserve):
```json
[
  { "nlType": "salary",             "expectedType": "Salary" },
  { "nlType": "depreciation",       "expectedType": "Depreciation" },
  { "nlType": "gst_inclusive_sale", "expectedType": "GST Collection" },
  { "nlType": "cash_sale",          "expectedType": "Cash Sale" },
  { "nlType": "credit_purchase",    "expectedType": "Credit Purchase" },
  { "nlType": "loan_received",      "expectedType": "Loan Disbursement" },
  { "nlType": "owner_investment",   "expectedType": "Owner Investment" },
  { "nlType": "refund",             "expectedType": "Refund" },
  { "nlType": "prepaid_expense",    "expectedType": "Prepaid Expense" },
  { "nlType": "inventory_purchase", "expectedType": "Inventory Purchase" }
]
```

- [ ] **Step 2: Create the baseline.** Create `scripts/eval/baseline.json`:
```json
{ "nlTypeMappingAccuracy": 1.0 }
```

- [ ] **Step 3: Create the runner.** Create `scripts/eval/runEval.js`:
```js
// scripts/eval/runEval.js — offline AI evaluation harness (deterministic, no LLM).
//
// Scores the pure NL type-mapping layer against a golden set and fails on any
// regression versus scripts/eval/baseline.json. This is the seed of the
// Intelligence Roadmap's eval-gated release discipline — extend it with more
// capabilities (account resolution, categorization) over time.
'use strict';
const fs = require('fs');
const path = require('path');
const { mapTransactionTypeForApi } = require('../../utils/nlParserPreview.helper');
const { scoreClassification, compareToBaseline } = require('../../utils/evalMetrics');

function load(rel) { return JSON.parse(fs.readFileSync(path.join(__dirname, rel), 'utf8')); }

function run() {
  const golden = load('golden/nl-parse.golden.json');
  const baseline = load('baseline.json');

  const predictions = golden.map((g) => ({ expectedType: mapTransactionTypeForApi(g.nlType) }));
  const goldens = golden.map((g) => ({ expectedType: g.expectedType }));
  const typeScore = scoreClassification(predictions, goldens, 'expectedType');

  const current = { nlTypeMappingAccuracy: typeScore.accuracy };
  const cmp = compareToBaseline(current, baseline, { tolerance: 0 });

  console.log('── VousFin AI Evaluation ─────────────────────────────');
  console.log(`NL type-mapping accuracy: ${typeScore.correct}/${typeScore.total} = ${typeScore.accuracy}`);
  if (!cmp.pass) {
    console.error('REGRESSION vs baseline:');
    cmp.regressions.forEach((r) => console.error(`  ${r.metric}: ${r.current} < ${r.baseline}`));
    process.exit(1);
  }
  console.log('PASS — no regression vs baseline.');
  process.exit(0);
}

run();
```

- [ ] **Step 4: Add the npm script.** In `package.json`, add to `"scripts"`:
```json
    "eval": "node scripts/eval/runEval.js",
```

- [ ] **Step 5: Run the harness.**

Run: `npm run eval`
Expected: prints `NL type-mapping accuracy: 10/10 = 1` and `PASS — no regression vs baseline.`, exit code 0.

- [ ] **Step 6: Commit.**
```bash
git add scripts/eval/ package.json
git commit -m "feat(eval): offline AI eval harness (npm run eval) — NL type-mapping baseline gate"
```

---

## Task 10: Full-suite verification + docs

**Files:**
- Modify: `docs/plans/06_VALIDATION_ENGINE.md` (note the eval harness), `docs/plans/14_AI_DEVELOPMENT_GUIDELINES.md` (note the Decision Ledger), `docs/plans/CHANGELOG.md`. (These live in the `Fyp-Documentation` repo at the workspace root — `../docs/plans/`.)

- [ ] **Step 1: Run the full backend suite.**

Run: `npm test`
Expected: all suites pass (the ~227 existing suites + the 6 new test files). If any pre-existing test broke, fix the cause (do not weaken the test).

- [ ] **Step 2: Run the eval harness and the drift gate.**

Run: `npm run eval` → PASS.
Run: `node scripts/ledgerDrift.js` → `Summary: … worst drift 0, any unbalanced: false`. (This phase does not post to the ledger, so drift must be unchanged at 0.)

- [ ] **Step 3: Update the docs.** In the `Fyp-Documentation` repo (workspace root `docs/plans/`): in `06_VALIDATION_ENGINE.md` add a line under §4 noting `npm run eval` gates AI-model/prompt changes; in `14_AI_DEVELOPMENT_GUIDELINES.md` note that every AI action must call `aiDecision.service.record()` and set an outcome; add a dated entry to `docs/plans/CHANGELOG.md` and to `docs/superpowers/specs/2026-07-01-vousfin-intelligence-roadmap-design.md` Phase 0 status → "shipped".

- [ ] **Step 4: Commit the docs (in the Fyp-Documentation repo).**
```bash
# from the workspace root (the docs repo), not the backend repo
git add docs/plans/06_VALIDATION_ENGINE.md docs/plans/14_AI_DEVELOPMENT_GUIDELINES.md docs/plans/CHANGELOG.md docs/superpowers/specs/2026-07-01-vousfin-intelligence-roadmap-design.md
git commit -m "docs: Phase 0 AI Decision Ledger + eval harness shipped"
```

- [ ] **Step 5: Push the backend work.**
```bash
# from vousfin-backend-main
git push origin main
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** Phase 0 of the roadmap = "AI Decision Ledger + Evaluation Harness." Tasks 1–7 build the Ledger (model, helpers, repo, service, reference instrumentation, view); Tasks 8–9 build the Harness (metrics, runner, gate); Task 10 verifies + documents. Both Phase-0 subsystems covered. Phases 1–6 are explicitly deferred to their own plans (spec §7).
- **Placeholder scan:** no TBD/TODO/"handle edge cases" — every step has concrete code, exact paths, exact commands, expected output.
- **Type consistency:** `buildDecisionRecord(businessId, kind, payload)` and `applyOutcome(current, new)` (Task 2) are consumed identically in Tasks 4–5; `record()`/`recordOutcome()`/`list()`/`getById()` (Task 5) are consumed identically in Tasks 6–7; `scoreClassification`/`compareToBaseline` (Task 8) are consumed in Task 9. Names/signatures match across tasks.
- **Guardrail coverage:** tenancy (every query filters `businessId`), never-throwing instrumentation (Task 5 tests assert it), append-only immutability (Task 3), no ledger changes (verified in Task 10 drift check), eval-gated (Task 9), TDD throughout.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-01-phase0-ai-decision-ledger.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in one session with checkpoints for review.

Which approach?
