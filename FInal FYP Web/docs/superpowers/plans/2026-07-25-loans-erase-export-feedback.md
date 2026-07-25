# Loans, Erase, Export & Feedback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four fixes — a loans-receivable sub-ledger with a real counterparty, a permanent transaction erase that provably keeps the books square, a full transaction export, and a readable admin feedback panel.

**Architecture:** Loans get their own control accounts (1145 / 1165) and a third `loan` direction in the existing open-item authority, so trade AR and the VE-5/6 reconcile are untouched. Erase is archive-first, rolls balances back with the exact inverse of the posting rule, and refuses to commit unless `computeDrift` reads 0 inside the same transaction. Export is a read-only endpoint reusing the list's filter schema and `EFFECTIVE_LINES_STAGE`. Feedback gets a detail modal plus three real bug fixes.

**Tech Stack:** Node/Express/Mongoose/Jest (backend), React 19/Vite/TanStack Query/Vitest + Testing Library (frontend), `exceljs` for xlsx.

**Spec:** `docs/superpowers/specs/2026-07-25-loans-erase-export-feedback-design.md`

## Global Constraints

- **Correctness > Performance > Convenience.** Never trade accounting integrity for cleaner code.
- **Never bypass the poster.** All ledger writes go through `ledgerPosting.postCompoundJournal` / `postBalancedJournal` / `transaction.service.createTransaction`. Never raw `JournalEntry.create`.
- **`scripts/ledgerDrift.js` must read 0** after every phase that touches the ledger (Phases 3 and 4).
- **Backend tests:** `npm test` from `vousfin-backend-main/`. Baseline is 301 suites / 2139 tests, zero failures. Never leave it lower.
- **Frontend tests:** `npx vitest run --reporter=json --outputFile=/tmp/vitest.json` from `vousfin-frontend-main/`. **The default reporter hangs** when the harness backgrounds a full-suite run — always use the json reporter + outputFile.
- **Product copy is plain language.** No accounting or FBR jargon as primary text — the reader is a non-accountant business owner. Jargon may appear as a secondary hint only.
- **Multi-tenant:** every query is scoped by `businessId`. No exceptions.
- **Run backend commands from `vousfin-backend-main/`, frontend commands from `vousfin-frontend-main/`.** They are separate git repos (submodules) — commit in the repo you changed.
- **Idempotency keys are mandatory** on system postings: `string | null | throw`, never undefined.

---

# Phase 1 — Feedback is readable

Smallest, pure bug-fix, zero accounting risk. Ship first.

## Task 1.1: Populate the feedback list and add a detail endpoint

**Files:**
- Modify: `vousfin-backend-main/services/userFeedback.service.js:23-33` (add populate), add `getById`
- Modify: `vousfin-backend-main/services/admin.service.js:314` (add passthrough)
- Modify: `vousfin-backend-main/controllers/admin.controller.js:138-151` (add `getFeedback`), export at `:244`
- Modify: `vousfin-backend-main/routes/v1/admin.routes.js:37` (add GET `/feedback/:id`)
- Test: `vousfin-backend-main/tests/unit/services/feedback.service.test.js` (existing file — append)

**Interfaces:**
- Consumes: nothing.
- Produces: `userFeedbackService.getById(id) → Promise<Object>` (throws `ApiError(404)`); `GET /api/v1/admin/feedback/:id` → `{ success, message, data }`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/services/feedback.service.test.js`:

```js
describe('userFeedbackService.getById()', () => {
  it('returns the populated feedback document', async () => {
    const doc = { _id: 'f1', message: 'Long message', userId: { email: 'a@b.com' } };
    const chain = { populate: jest.fn().mockReturnThis(), lean: jest.fn().mockResolvedValue(doc) };
    jest.spyOn(Feedback, 'findById').mockReturnValue(chain);

    const result = await userFeedbackService.getById('f1');

    expect(result).toEqual(doc);
    expect(chain.populate).toHaveBeenCalledWith('userId', 'fullName email');
    expect(chain.populate).toHaveBeenCalledWith('businessId', 'businessName');
  });

  it('throws 404 when the feedback does not exist', async () => {
    const chain = { populate: jest.fn().mockReturnThis(), lean: jest.fn().mockResolvedValue(null) };
    jest.spyOn(Feedback, 'findById').mockReturnValue(chain);

    await expect(userFeedbackService.getById('missing')).rejects.toMatchObject({ statusCode: 404 });
  });
});

describe('userFeedbackService.listAll() population', () => {
  it('populates the submitter so the admin table can show an email', async () => {
    const chain = {
      sort: jest.fn().mockReturnThis(),
      skip: jest.fn().mockReturnThis(),
      limit: jest.fn().mockReturnThis(),
      populate: jest.fn().mockReturnThis(),
      lean: jest.fn().mockResolvedValue([]),
    };
    jest.spyOn(Feedback, 'find').mockReturnValue(chain);
    jest.spyOn(Feedback, 'countDocuments').mockResolvedValue(0);

    await userFeedbackService.listAll({});

    expect(chain.populate).toHaveBeenCalledWith('userId', 'fullName email');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/feedback.service.test.js -t "getById" 2>&1 | tail -20
```

Expected: FAIL — `userFeedbackService.getById is not a function`.

- [ ] **Step 3: Implement**

In `services/userFeedback.service.js`, change the `listAll` query at line 29 to populate, and add `getById` after `listAll`:

```js
  async listAll({ status, type, page = 1, limit = 50 } = {}) {
    const query = {};
    if (status) query.status = status;
    if (type)   query.type   = type;
    const skip  = (page - 1) * limit;
    const [data, total] = await Promise.all([
      Feedback.find(query)
        .sort({ createdAt: -1 })
        .skip(skip)
        .limit(Number(limit))
        .populate('userId', 'fullName email')
        .populate('businessId', 'businessName')
        .lean(),
      Feedback.countDocuments(query),
    ]);
    return { data, total, page: Number(page), limit: Number(limit) };
  }

  /**
   * One feedback item, fully populated — powers the admin detail view.
   */
  async getById(id) {
    const doc = await Feedback.findById(id)
      .populate('userId', 'fullName email')
      .populate('businessId', 'businessName')
      .lean();
    if (!doc) throw new ApiError(404, 'Feedback not found');
    return doc;
  }
```

In `services/admin.service.js`, after line 314:

```js
  async getFeedback(id) { return userFeedbackService.getById(id); }
```

In `controllers/admin.controller.js`, after `listFeedback` (line 144):

```js
const getFeedback = async (req, res, next) => {
  try {
    const doc = await adminService.getFeedback(req.params.id);
    ApiResponse.success(res, doc, 'Feedback retrieved');
  } catch (err) { next(err); }
};
```

Add `getFeedback,` to the exports block at line 244.

In `routes/v1/admin.routes.js`, after line 37:

```js
router.get('/feedback/:id',     adminController.getFeedback);
```

> **Route order matters:** `/feedback/:id` must come *after* `/feedback` (line 37) and *before* any wildcard. Express matches in declaration order.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/feedback.service.test.js 2>&1 | tail -20
```

Expected: PASS, all tests in the file green.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add services/userFeedback.service.js services/admin.service.js controllers/admin.controller.js routes/v1/admin.routes.js tests/unit/services/feedback.service.test.js && git commit -m "feat(admin): populate feedback submitter and add detail endpoint"
```

## Task 1.2: Feedback detail modal

**Files:**
- Create: `vousfin-frontend-main/src/components/modals/FeedbackDetailModal.jsx`
- Create: `vousfin-frontend-main/src/components/modals/FeedbackDetailModal.test.jsx`
- Modify: `vousfin-frontend-main/src/services/admin.service.js:33-37` (add `getFeedback`)

**Interfaces:**
- Consumes: `GET /admin/feedback/:id` from Task 1.1; `Modal` from `@/components/modals/Modal` (props: `isOpen`, `onClose`, `title`, `children`, `className`).
- Produces: `<FeedbackDetailModal feedback={obj|null} isOpen onClose onSaveNote={(id, note) => Promise} onSaveStatus={(id, status) => Promise} />`.

- [ ] **Step 1: Write the failing test**

Create `src/components/modals/FeedbackDetailModal.test.jsx`:

```jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FeedbackDetailModal from './FeedbackDetailModal'

const feedback = {
  _id: 'f1',
  type: 'bug',
  subject: 'Cannot export',
  message: 'Line one.\nLine two of a very long message that used to be clipped.',
  rating: 4,
  status: 'new',
  adminNote: '',
  name: 'Ali Raza',
  email: 'ali@example.com',
  userId: { fullName: 'Ali Raza', email: 'ali@example.com' },
  businessId: { businessName: 'Code Hub' },
  createdAt: '2026-07-20T10:00:00.000Z',
}

describe('FeedbackDetailModal', () => {
  it('shows the complete message, not a clipped preview', () => {
    render(<FeedbackDetailModal feedback={feedback} isOpen onClose={() => {}} />)
    expect(screen.getByText(/Line two of a very long message/)).toBeInTheDocument()
  })

  it('shows the submitter, business and subject', () => {
    render(<FeedbackDetailModal feedback={feedback} isOpen onClose={() => {}} />)
    expect(screen.getByText('Cannot export')).toBeInTheDocument()
    expect(screen.getByText(/ali@example.com/)).toBeInTheDocument()
    expect(screen.getByText(/Code Hub/)).toBeInTheDocument()
  })

  it('falls back to the plain email when userId is not populated', () => {
    const anon = { ...feedback, userId: null }
    render(<FeedbackDetailModal feedback={anon} isOpen onClose={() => {}} />)
    expect(screen.getByText(/ali@example.com/)).toBeInTheDocument()
  })

  it('saves the note once on click, not on every keystroke', () => {
    const onSaveNote = vi.fn()
    render(<FeedbackDetailModal feedback={feedback} isOpen onClose={() => {}} onSaveNote={onSaveNote} />)

    const box = screen.getByPlaceholderText(/note/i)
    fireEvent.change(box, { target: { value: 'checked' } })
    fireEvent.change(box, { target: { value: 'checked it' } })
    expect(onSaveNote).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /save note/i }))
    expect(onSaveNote).toHaveBeenCalledTimes(1)
    expect(onSaveNote).toHaveBeenCalledWith('f1', 'checked it')
  })

  it('renders nothing when there is no feedback selected', () => {
    const { container } = render(<FeedbackDetailModal feedback={null} isOpen={false} onClose={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd vousfin-frontend-main && npx vitest run src/components/modals/FeedbackDetailModal.test.jsx --reporter=json --outputFile=/tmp/vitest-fb.json 2>&1 | tail -15
```

Expected: FAIL — cannot resolve `./FeedbackDetailModal`.

- [ ] **Step 3: Implement**

Create `src/components/modals/FeedbackDetailModal.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { Star } from 'lucide-react'
import Modal from './Modal'

const TYPE_STYLES = {
  bug:     'bg-negative/20 text-negative',
  feature: 'bg-accent/20 text-accent',
  question:'bg-accent/20 text-accent',
  praise:  'bg-positive/20 text-positive',
}

const STATUS_STYLES = {
  new:      'bg-highlight/20 text-highlight',
  reviewed: 'bg-accent/20 text-accent',
  resolved: 'bg-positive/20 text-positive',
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-label uppercase tracking-wider text-text-muted">{label}</div>
      <div className="mt-0.5 text-small text-text-primary">{children}</div>
    </div>
  )
}

export default function FeedbackDetailModal({ feedback, isOpen, onClose, onSaveNote, onSaveStatus }) {
  const [note, setNote] = useState('')

  // Reset the draft whenever a different item is opened, so the previous
  // item's unsaved note can never be written onto this one.
  useEffect(() => { setNote(feedback?.adminNote || '') }, [feedback?._id, feedback?.adminNote])

  if (!feedback) return null

  const submitterName  = feedback.userId?.fullName || feedback.name || 'Anonymous'
  const submitterEmail = feedback.userId?.email || feedback.email || ''
  const businessName   = feedback.businessId?.businessName || '—'
  const typeLabel      = feedback.type ? feedback.type.charAt(0).toUpperCase() + feedback.type.slice(1) : '—'
  const statusLabel    = feedback.status ? feedback.status.charAt(0).toUpperCase() + feedback.status.slice(1) : '—'

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={feedback.subject || 'Feedback'} className="max-w-2xl">
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-label font-semibold ${TYPE_STYLES[feedback.type] || 'bg-text-muted/20 text-text-muted'}`}>
            {typeLabel}
          </span>
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-label font-semibold ${STATUS_STYLES[feedback.status] || 'bg-text-muted/20 text-text-muted'}`}>
            {statusLabel}
          </span>
          {feedback.rating ? (
            <span className="flex items-center gap-0.5" aria-label={`Rated ${feedback.rating} out of 5`}>
              {[1, 2, 3, 4, 5].map((s) => (
                <Star key={s} className={`h-3.5 w-3.5 ${s <= feedback.rating ? 'text-positive' : 'text-text-muted'}`} />
              ))}
            </span>
          ) : null}
        </div>

        <div>
          <div className="text-label uppercase tracking-wider text-text-muted">What they said</div>
          <p className="mt-1 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg border border-glass bg-glass-panel/40 p-3 text-small leading-relaxed text-text-primary">
            {feedback.message}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="From">
            {submitterName}
            {submitterEmail ? <span className="block text-text-secondary">{submitterEmail}</span> : null}
          </Field>
          <Field label="Business">{businessName}</Field>
          <Field label="Sent">
            {feedback.createdAt ? new Date(feedback.createdAt).toLocaleString() : '—'}
          </Field>
        </div>

        {onSaveStatus ? (
          <div>
            <label htmlFor="fb-status" className="text-label uppercase tracking-wider text-text-muted">Status</label>
            <select
              id="fb-status"
              value={feedback.status}
              onChange={(e) => onSaveStatus(feedback._id, e.target.value)}
              className="mt-1 w-full rounded-lg border border-glass bg-glass-panel px-3 py-2 text-small focus:border-accent/40 focus:outline-none"
            >
              <option value="new">New</option>
              <option value="reviewed">Reviewed</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
        ) : null}

        {onSaveNote ? (
          <div>
            <label htmlFor="fb-note" className="text-label uppercase tracking-wider text-text-muted">Your note</label>
            <textarea
              id="fb-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note for your team…"
              rows={3}
              className="mt-1 w-full resize-none rounded-lg border border-glass bg-glass-panel/40 px-3 py-2 text-small focus:border-accent/40 focus:outline-none"
            />
            <button
              onClick={() => onSaveNote(feedback._id, note)}
              className="mt-2 rounded-lg bg-accent/20 px-3 py-1.5 text-small text-accent transition-colors hover:bg-accent/30"
            >
              Save note
            </button>
          </div>
        ) : null}
      </div>
    </Modal>
  )
}
```

Add to `src/services/admin.service.js` after line 36:

```js
  getFeedback: (id) =>
    api.get(`/admin/feedback/${id}`),
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd vousfin-frontend-main && npx vitest run src/components/modals/FeedbackDetailModal.test.jsx --reporter=json --outputFile=/tmp/vitest-fb.json 2>&1 | tail -15
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-frontend-main && git add src/components/modals/FeedbackDetailModal.jsx src/components/modals/FeedbackDetailModal.test.jsx src/services/admin.service.js && git commit -m "feat(admin): feedback detail modal"
```

## Task 1.3: Wire the modal into the admin table and fix the three bugs

**Files:**
- Modify: `vousfin-frontend-main/src/pages/admin/AdminPage.jsx:437-644` (the whole `FeedbackTab`)

**Interfaces:**
- Consumes: `FeedbackDetailModal` (Task 1.2), `adminService.getFeedback` (Task 1.2).
- Produces: nothing downstream.

- [ ] **Step 1: Fix the malformed status badge (bug 1)**

Replace lines 569-578 — the ``className={`inline-flex>`` template literal never closes before the ternary, so the badge gets a garbage className:

```jsx
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-label font-semibold ${
                    f.status === 'new' ? 'bg-highlight/20 text-highlight' :
                    f.status === 'reviewed' ? 'bg-accent/20 text-accent' :
                    f.status === 'resolved' ? 'bg-positive/20 text-positive' :
                    'bg-text-muted/20 text-text-muted'
                  }`}>
                    {f.status.charAt(0).toUpperCase() + f.status.slice(1)}
                  </span>
                </td>
```

- [ ] **Step 2: Replace the per-keystroke note box (bug 2) and add row-open**

Replace the whole Actions cell (lines 579-619) with a status dropdown only — the note now lives in the modal, so the textarea that fired a `ConfirmDialog` on every keystroke is deleted outright:

```jsx
                <td className="px-4 py-3 text-right font-semibold" onClick={(e) => e.stopPropagation()}>
                  <select
                    value={f.status}
                    onChange={(e) => setConfirm({ type: 'updateStatus', id: f._id, extra: e.target.value })}
                    className="border border-glass px-2 py-1 rounded-lg text-xs bg-glass-panel focus:outline-none focus:border-accent/40"
                    aria-label="Change status"
                  >
                    <option value="new">New</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="resolved">Resolved</option>
                  </select>
                </td>
```

Make the row itself open the detail — replace the `<tr>` opening tag at line 541:

```jsx
              <tr
                key={f._id}
                onClick={() => setSelected(f)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(f) } }}
                tabIndex={0}
                role="button"
                aria-label={`Open feedback: ${f.subject || 'no subject'}`}
                className="border-b border-glass/50 last:border-0 hover:bg-glass-hover/30 transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-accent/40"
              >
```

- [ ] **Step 3: Fix the submitter column (bug 3) and add the modal**

Replace line 565:

```jsx
                <td className="px-4 py-3 text-text-secondary">{f.userId?.email || f.email || f.name || '—'}</td>
```

Add the selection state next to the other `useState` calls (after line 443):

```jsx
  const [selected, setSelected] = useState(null)
```

Add the modal just before the closing `</div>` of the component (after the `ConfirmDialog` at line 641):

```jsx
      <FeedbackDetailModal
        feedback={selected}
        isOpen={!!selected}
        onClose={() => setSelected(null)}
        onSaveStatus={(id, status) => act(() => adminService.updateFeedback(id, { status }), 'Status updated')}
        onSaveNote={(id, adminNote) => act(() => adminService.updateFeedback(id, { adminNote }), 'Note saved')}
      />
```

Add the import at the top of the file, alongside the other component imports:

```jsx
import FeedbackDetailModal from '@/components/modals/FeedbackDetailModal'
```

Delete the now-dead `updateNote` branches in `handleConfirm` (line 471) and in the `ConfirmDialog` title/message ternaries (lines 632, 636) — only `updateStatus` reaches the dialog now.

- [ ] **Step 4: Verify the build and full test suite**

```bash
cd vousfin-frontend-main && npm run build 2>&1 | tail -8
```

Expected: build succeeds, no errors.

```bash
cd vousfin-frontend-main && npx vitest run --reporter=json --outputFile=/tmp/vitest-all.json 2>&1 | tail -8 && node -e "const r=require('/tmp/vitest-all.json');console.log('files',r.numTotalTestSuites,'tests',r.numTotalTests,'failed',r.numFailedTests)"
```

Expected: `failed 0`.

- [ ] **Step 5: Commit**

```bash
cd vousfin-frontend-main && git add src/pages/admin/AdminPage.jsx && git commit -m "fix(admin): open feedback in one click; fix badge className, per-keystroke confirm, submitter column"
```

- [ ] **Step 6: Live-verify in the browser**

Start the dev server via `preview_start` with the frontend config, log in as an admin, open Admin → Feedback, click a row, confirm the full message renders and Save note fires exactly one request (check `read_network_requests`). Screenshot the open modal.

---

**Phase 1 checkpoint.** Feedback is fully usable. Backend suite green, frontend suite green, build clean. Stop and report before starting Phase 2.

---

# Phase 2 — Export transactions

Additive, read-only. No writes, no ledger risk.

## Task 2.1: Extract the filter builder so export and list can never diverge

`findManyWithFilters` (`repositories/transaction.repository.js:115-240`) builds its Mongo query inline. The export must apply *identical* filters — copying the logic would guarantee drift. Extract it once, use it twice.

**Files:**
- Modify: `vousfin-backend-main/repositories/transaction.repository.js:115-190` (extract `buildFilterQuery`)
- Test: `vousfin-backend-main/tests/unit/repositories/transaction.repository.filters.test.js` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `transactionRepository.buildFilterQuery(businessId, filters) → Object` (a Mongo query object).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/repositories/transaction.repository.filters.test.js`:

```js
'use strict';
const mongoose = require('mongoose');
const repo = require('../../../repositories/transaction.repository');
const { TRANSACTION_TYPES, PAYMENT_STATUS } = require('../../../config/constants');

const BIZ = new mongoose.Types.ObjectId().toString();
const ACC = new mongoose.Types.ObjectId().toString();

describe('transactionRepository.buildFilterQuery()', () => {
  it('always scopes to the business and excludes archived entries', () => {
    const q = repo.buildFilterQuery(BIZ, {});
    expect(String(q.businessId)).toBe(BIZ);
    expect(q.isArchived).toEqual({ $ne: true });
  });

  it('applies an inclusive date range', () => {
    const q = repo.buildFilterQuery(BIZ, { startDate: '2026-01-01', endDate: '2026-01-31' });
    expect(q.transactionDate.$gte).toEqual(new Date('2026-01-01'));
    expect(q.transactionDate.$lte).toEqual(new Date('2026-01-31'));
  });

  it('matches an account on either side of the entry', () => {
    const q = repo.buildFilterQuery(BIZ, { accountId: ACC });
    expect(q.$or).toHaveLength(2);
    expect(String(q.$or[0].debitAccountId)).toBe(ACC);
    expect(String(q.$or[1].creditAccountId)).toBe(ACC);
  });

  it('ignores an unknown transaction type rather than returning nothing', () => {
    const q = repo.buildFilterQuery(BIZ, { transactionType: 'Not A Real Type' });
    expect(q.transactionType).toBeUndefined();
  });

  it('keeps a valid transaction type', () => {
    const q = repo.buildFilterQuery(BIZ, { transactionType: TRANSACTION_TYPES.EXPENSE });
    expect(q.transactionType).toBe(TRANSACTION_TYPES.EXPENSE);
  });

  it('restricts to open items when hasOutstandingBalance is set', () => {
    const q = repo.buildFilterQuery(BIZ, { hasOutstandingBalance: 'true' });
    expect(q.remainingBalance).toEqual({ $gt: 0 });
    expect(q.paymentStatus.$in).toContain(PAYMENT_STATUS.UNPAID);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/repositories/transaction.repository.filters.test.js 2>&1 | tail -15
```

Expected: FAIL — `repo.buildFilterQuery is not a function`.

- [ ] **Step 3: Extract the method**

In `repositories/transaction.repository.js`, add this method immediately before `findManyWithFilters` (line 115). It is the exact body of lines 125-190, moved verbatim — no behaviour change:

```js
  /**
   * THE filter query for journal-entry lists. Extracted so the list endpoint and
   * the export endpoint can never drift apart: what the screen shows is exactly
   * what the file contains. Callers add their own sort/skip/limit.
   *
   * @param {string} businessId
   * @param {Object} filters  startDate, endDate, transactionType, minAmount,
   *   maxAmount, accountId, customerId, vendorId, status, paymentStatus,
   *   hasOutstandingBalance, search
   * @returns {Object} a Mongo query object
   */
  buildFilterQuery(businessId, filters = {}) {
    const validBusinessId = sanitizeAndValidateId(businessId);
    const query = {
      businessId: validBusinessId,
      isArchived: { $ne: true },
    };

    if (filters.startDate || filters.endDate) {
      query.transactionDate = {};
      if (filters.startDate) query.transactionDate.$gte = new Date(filters.startDate);
      if (filters.endDate) query.transactionDate.$lte = new Date(filters.endDate);
    }

    if (filters.transactionType && Object.values(TRANSACTION_TYPES).includes(filters.transactionType)) {
      query.transactionType = filters.transactionType;
    }

    if (filters.minAmount !== undefined || filters.maxAmount !== undefined) {
      query.amount = {};
      if (filters.minAmount !== undefined) query.amount.$gte = parseFloat(filters.minAmount);
      if (filters.maxAmount !== undefined) query.amount.$lte = parseFloat(filters.maxAmount);
    }

    if (filters.accountId) {
      const validAccountId = sanitizeAndValidateId(filters.accountId);
      query.$or = [
        { debitAccountId: validAccountId },
        { creditAccountId: validAccountId },
      ];
    }

    if (filters.status && Object.values(JOURNAL_STATUS).includes(filters.status)) {
      query.status = filters.status;
    }

    if (filters.paymentStatus && Object.values(PAYMENT_STATUS).includes(filters.paymentStatus)) {
      query.paymentStatus = filters.paymentStatus;
    }

    if (filters.customerId) {
      query.customerId = sanitizeAndValidateId(filters.customerId);
    }

    if (filters.vendorId) {
      query.vendorId = sanitizeAndValidateId(filters.vendorId);
    }

    if (filters.hasOutstandingBalance === true || filters.hasOutstandingBalance === 'true') {
      query.remainingBalance = { $gt: 0 };
      query.paymentStatus = { $in: [PAYMENT_STATUS.UNPAID, PAYMENT_STATUS.PARTIALLY_PAID] };
    }

    if (filters.search) {
      query.$text = { $search: filters.search };
    }

    return query;
  }
```

Then replace lines 125-190 inside `findManyWithFilters` (everything from `const query = {` through the `$text` block) with a single line:

```js
    const query = this.buildFilterQuery(businessId, filters);
```

Leave `sanitizeAndValidateId(businessId)` on line 116 alone — `validBusinessId` is not otherwise used in the method after the extraction, so delete that line only if lint flags it.

- [ ] **Step 4: Run the test and the existing repository tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/repositories/ 2>&1 | tail -15
```

Expected: PASS — the new file green **and** every pre-existing repository test still green (this is a pure refactor; any red here means the extraction changed behaviour).

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add repositories/transaction.repository.js tests/unit/repositories/transaction.repository.filters.test.js && git commit -m "refactor(transactions): extract buildFilterQuery so list and export share one filter"
```

## Task 2.2: The export builder

**Files:**
- Create: `vousfin-backend-main/utils/transactionExport.utils.js`
- Test: `vousfin-backend-main/tests/unit/utils/transactionExport.utils.test.js`

**Interfaces:**
- Consumes: `transactionRepository.buildFilterQuery` (Task 2.1); `EFFECTIVE_LINES_STAGE` from `repositories/transaction.repository.js:40`; `exceljs`.
- Produces:
  - `buildExportRows(businessId, filters) → Promise<{ entries: Array, lines: Array, truncated: boolean }>`
  - `toCsv(entries) → string`
  - `toXlsx({ entries, lines, meta }) → Promise<Buffer>`
  - `EXPORT_ROW_CAP = 50000`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/utils/transactionExport.utils.test.js`:

```js
'use strict';
const { toCsv, EXPORT_ROW_CAP } = require('../../../utils/transactionExport.utils');

const simple = {
  transactionDate: new Date('2026-07-20T00:00:00.000Z'),
  entryId: '68a1',
  reference: 'INV-001',
  description: 'Sale to Ali',
  transactionType: 'Credit Sale',
  debitAccount: '1110 Accounts Receivable',
  creditAccount: '4010 Sales Revenue',
  amount: 1250,
  currencyCode: 'PKR',
  exchangeRate: 1,
  baseAmount: 1250,
  party: 'Ali Raza',
  paymentStatus: 'unpaid',
  remainingBalance: 1250,
  taxAmount: 0,
  costCenter: '',
  source: 'manual',
  enteredBy: 'Owner',
  enteredAt: new Date('2026-07-20T09:30:00.000Z'),
  status: 'posted',
};

const split = { ...simple, entryId: '68a2', debitAccount: '-- Split --', creditAccount: '-- Split --' };

describe('toCsv()', () => {
  it('emits a header row with human-readable column names', () => {
    const csv = toCsv([simple]);
    const header = csv.split('\n')[0];
    expect(header).toContain('"Date"');
    expect(header).toContain('"Debit Account"');
    expect(header).toContain('"Credit Account"');
    expect(header).toContain('"Base Amount"');
  });

  it('writes one row per entry', () => {
    const csv = toCsv([simple, split]);
    expect(csv.trim().split('\n')).toHaveLength(3); // header + 2
  });

  it('marks compound entries as a split', () => {
    const csv = toCsv([split]);
    expect(csv).toContain('-- Split --');
  });

  it('escapes embedded quotes so the file cannot be broken by a description', () => {
    const csv = toCsv([{ ...simple, description: 'He said "hello"' }]);
    expect(csv).toContain('"He said ""hello"""');
  });

  it('produces a valid header-only file for an empty result', () => {
    const csv = toCsv([]);
    expect(csv.split('\n')[0]).toContain('"Date"');
    expect(csv.trim().split('\n')).toHaveLength(1);
  });

  it('caps exports at 50,000 rows', () => {
    expect(EXPORT_ROW_CAP).toBe(50000);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/utils/transactionExport.utils.test.js 2>&1 | tail -15
```

Expected: FAIL — cannot find module `transactionExport.utils`.

- [ ] **Step 3: Implement the util**

Create `utils/transactionExport.utils.js`:

```js
'use strict';
/**
 * transactionExport.utils — turn journal entries into a file a business owner
 * (or their accountant) can actually use.
 *
 * TWO SHEETS, on purpose. Sheet 1 is one row per transaction with the columns
 * people ask for (date, debit account, credit account, amount). That shape
 * cannot represent a compound entry — payroll, tax and inventory postings touch
 * 3+ accounts — so those rows say "-- Split --" and Sheet 2 carries every debit
 * and credit as its own row. Sheet 2 is what ties to the trial balance.
 */
const ExcelJS = require('exceljs');
const mongoose = require('mongoose');
const JournalEntry = require('../models/JournalEntry.model');
const transactionRepository = require('../repositories/transaction.repository');
const { EFFECTIVE_LINES_STAGE } = require('../repositories/transaction.repository');

const EXPORT_ROW_CAP = 50000;
const SPLIT = '-- Split --';

const ENTRY_COLUMNS = [
  { key: 'transactionDate',  label: 'Date',             width: 12 },
  { key: 'entryId',          label: 'Entry ID',         width: 26 },
  { key: 'reference',        label: 'Reference',        width: 16 },
  { key: 'description',      label: 'Details',          width: 40 },
  { key: 'transactionType',  label: 'Type',             width: 18 },
  { key: 'debitAccount',     label: 'Debit Account',    width: 30 },
  { key: 'creditAccount',    label: 'Credit Account',   width: 30 },
  { key: 'amount',           label: 'Amount',           width: 14 },
  { key: 'currencyCode',     label: 'Currency',         width: 10 },
  { key: 'exchangeRate',     label: 'Rate',             width: 10 },
  { key: 'baseAmount',       label: 'Base Amount',      width: 14 },
  { key: 'party',            label: 'Customer / Vendor',width: 24 },
  { key: 'paymentStatus',    label: 'Payment Status',   width: 16 },
  { key: 'remainingBalance', label: 'Still Owed',       width: 14 },
  { key: 'taxAmount',        label: 'Tax',              width: 12 },
  { key: 'costCenter',       label: 'Cost Centre',      width: 18 },
  { key: 'source',           label: 'Entered Via',      width: 14 },
  { key: 'enteredBy',        label: 'Entered By',       width: 20 },
  { key: 'enteredAt',        label: 'Entered At',       width: 20 },
  { key: 'status',           label: 'Status',           width: 14 },
];

const LINE_COLUMNS = [
  { key: 'transactionDate', label: 'Date',         width: 12 },
  { key: 'entryId',         label: 'Entry ID',     width: 26 },
  { key: 'lineNo',          label: 'Line',         width: 8  },
  { key: 'accountCode',     label: 'Account Code', width: 14 },
  { key: 'accountName',     label: 'Account Name', width: 32 },
  { key: 'debit',           label: 'Debit',        width: 14 },
  { key: 'credit',          label: 'Credit',       width: 14 },
  { key: 'description',     label: 'Details',      width: 36 },
  { key: 'costCenter',      label: 'Cost Centre',  width: 18 },
];

const r2 = (v) => Math.round((Number(v) || 0) * 100) / 100;
const fmtDate = (d) => (d ? new Date(d).toISOString().slice(0, 10) : '');
const acctLabel = (a) => (a ? `${a.accountCode || ''} ${a.accountName || ''}`.trim() : '');

/**
 * Read every entry matching the filters, plus its expanded ledger lines.
 * Reads through EFFECTIVE_LINES_STAGE so a compound entry expands to its real
 * lines and a legacy 2-account entry synthesises its pair — identical to how
 * every report reads the ledger.
 */
async function buildExportRows(businessId, filters = {}) {
  const query = transactionRepository.buildFilterQuery(businessId, filters);

  const docs = await JournalEntry.find(query)
    .populate('debitAccountId',  'accountCode accountName')
    .populate('creditAccountId', 'accountCode accountName')
    .populate('customerId', 'fullName businessName')
    .populate('vendorId',   'vendorName')
    .populate('createdBy',  'fullName email')
    .populate('costCenterId', 'name')
    .sort({ transactionDate: -1, createdAt: -1, _id: -1 })
    .limit(EXPORT_ROW_CAP + 1)
    .lean();

  const truncated = docs.length > EXPORT_ROW_CAP;
  const entries = (truncated ? docs.slice(0, EXPORT_ROW_CAP) : docs).map((d) => {
    const compound = Array.isArray(d.journalLines) && d.journalLines.length > 2;
    const party = d.customerId
      ? (d.customerId.fullName || d.customerId.businessName || '')
      : (d.vendorId?.vendorName || '');
    return {
      transactionDate: fmtDate(d.transactionDate),
      entryId: String(d._id),
      reference: d.invoiceNumber || d.transactionReference || '',
      description: d.description || '',
      transactionType: d.transactionType || '',
      debitAccount:  compound ? SPLIT : acctLabel(d.debitAccountId),
      creditAccount: compound ? SPLIT : acctLabel(d.creditAccountId),
      amount: r2(d.amount),
      currencyCode: d.currencyCode || '',
      exchangeRate: d.exchangeRate ?? 1,
      baseAmount: r2(d.baseCurrencyAmount ?? d.amount),
      party,
      paymentStatus: d.paymentStatus || '',
      remainingBalance: d.remainingBalance == null ? '' : r2(d.remainingBalance),
      taxAmount: r2(d.taxAmount),
      costCenter: d.costCenterId?.name || '',
      source: d.transactionSource || d.inputMethod || '',
      enteredBy: d.createdBy?.fullName || d.createdBy?.email || '',
      enteredAt: d.createdAt ? new Date(d.createdAt).toISOString().slice(0, 16).replace('T', ' ') : '',
      status: d.status || '',
    };
  });

  const ids = entries.map((e) => new mongoose.Types.ObjectId(e.entryId));
  const lines = ids.length ? await JournalEntry.aggregate([
    { $match: { _id: { $in: ids } } },
    EFFECTIVE_LINES_STAGE,
    { $unwind: { path: '$effectiveLines', includeArrayIndex: 'lineIdx' } },
    {
      $lookup: {
        from: 'chartofaccounts',
        localField: 'effectiveLines.accountId',
        foreignField: '_id',
        as: 'acc',
        pipeline: [{ $project: { accountCode: 1, accountName: 1 } }],
      },
    },
    { $unwind: { path: '$acc', preserveNullAndEmptyArrays: true } },
    { $sort: { transactionDate: -1, _id: -1, lineIdx: 1 } },
    {
      $project: {
        _id: 0,
        transactionDate: 1,
        entryId: { $toString: '$_id' },
        lineNo: { $add: ['$lineIdx', 1] },
        accountCode: { $ifNull: ['$acc.accountCode', ''] },
        accountName: { $ifNull: ['$acc.accountName', ''] },
        debit:  { $cond: [{ $eq: ['$effectiveLines.type', 'debit'] },  '$effectiveLines.amount', 0] },
        credit: { $cond: [{ $eq: ['$effectiveLines.type', 'credit'] }, '$effectiveLines.amount', 0] },
        description: { $ifNull: ['$effectiveLines.description', '$description'] },
      },
    },
  ]) : [];

  const lineRows = lines.map((l) => ({
    ...l,
    transactionDate: fmtDate(l.transactionDate),
    debit: r2(l.debit),
    credit: r2(l.credit),
    costCenter: '',
  }));

  return { entries, lines: lineRows, truncated };
}

/** Sheet 1's columns as CSV. CSV has no second sheet — the caller says so. */
function toCsv(entries) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const rows = [ENTRY_COLUMNS.map((c) => esc(c.label)).join(',')];
  for (const e of entries) {
    rows.push(ENTRY_COLUMNS.map((c) => esc(e[c.key])).join(','));
  }
  return rows.join('\n');
}

function _sheet(wb, name, columns, rows) {
  const ws = wb.addWorksheet(name);
  ws.columns = columns.map((c) => ({ header: c.label, key: c.key, width: c.width }));
  ws.getRow(1).font = { bold: true };
  ws.getRow(1).alignment = { vertical: 'middle' };
  ws.views = [{ state: 'frozen', ySplit: 1 }];
  rows.forEach((r) => ws.addRow(r));
  return ws;
}

/** Both sheets, with a totals row on Sheet 2 that proves debits = credits. */
async function toXlsx({ entries, lines, meta = {} }) {
  const wb = new ExcelJS.Workbook();
  wb.creator = 'VousFin';
  wb.created = new Date();

  _sheet(wb, 'Transactions', ENTRY_COLUMNS, entries);

  const ws2 = _sheet(wb, 'Ledger lines', LINE_COLUMNS, lines);
  const totalDebit  = r2(lines.reduce((s, l) => s + (l.debit  || 0), 0));
  const totalCredit = r2(lines.reduce((s, l) => s + (l.credit || 0), 0));
  const totals = ws2.addRow({ accountName: 'TOTAL', debit: totalDebit, credit: totalCredit });
  totals.font = { bold: true };

  const info = wb.addWorksheet('About');
  info.columns = [{ width: 22 }, { width: 60 }];
  info.addRows([
    ['Business',      meta.businessName || ''],
    ['Base currency', meta.baseCurrency || ''],
    ['Period',        meta.period || 'All dates'],
    ['Generated',     new Date().toISOString().slice(0, 16).replace('T', ' ')],
    ['Rows',          String(entries.length)],
    [''],
    ['Note', 'Entries that touch more than two accounts show "-- Split --" on the Transactions sheet. Their full detail is on the Ledger lines sheet.'],
  ]);
  info.getColumn(1).font = { bold: true };

  return wb.xlsx.writeBuffer();
}

module.exports = { buildExportRows, toCsv, toXlsx, EXPORT_ROW_CAP, ENTRY_COLUMNS, LINE_COLUMNS };
```

> `EFFECTIVE_LINES_STAGE` must be exported from `repositories/transaction.repository.js`. It already is (line 539 references it inside the class; confirm the module's `module.exports` includes it — if not, add `module.exports.EFFECTIVE_LINES_STAGE = EFFECTIVE_LINES_STAGE;` at the bottom of that file).

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd vousfin-backend-main && npx jest tests/unit/utils/transactionExport.utils.test.js 2>&1 | tail -15
```

Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add utils/transactionExport.utils.js tests/unit/utils/transactionExport.utils.test.js repositories/transaction.repository.js && git commit -m "feat(export): transaction export builder — two sheets, compound-safe"
```

## Task 2.3: The export endpoint

**Files:**
- Modify: `vousfin-backend-main/controllers/transaction.controller.js` (add `exportTransactions`, export it at `:1443`)
- Modify: `vousfin-backend-main/validations/transaction.validation.js:261` (add `transactionExportSchema`, export at `:312`)
- Modify: `vousfin-backend-main/routes/v1/transaction.routes.js:77` (add the route **before** `/:id`)
- Test: `vousfin-backend-main/tests/unit/controllers/transaction.export.test.js`

**Interfaces:**
- Consumes: `buildExportRows`, `toCsv`, `toXlsx`, `EXPORT_ROW_CAP` (Task 2.2).
- Produces: `GET /api/v1/transactions/export` → a file download.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/controllers/transaction.export.test.js`:

```js
'use strict';
jest.mock('../../../utils/transactionExport.utils', () => ({
  buildExportRows: jest.fn(),
  toCsv: jest.fn(() => 'CSV_BODY'),
  toXlsx: jest.fn(async () => Buffer.from('XLSX_BODY')),
  EXPORT_ROW_CAP: 50000,
}));
jest.mock('../../../services/business.service', () => ({
  getBusinessById: jest.fn(async () => ({ businessName: 'Code Hub', currency: 'PKR' })),
}));

const exportUtils = require('../../../utils/transactionExport.utils');
const transactionController = require('../../../controllers/transaction.controller');

const mockRes = () => {
  const res = {};
  res.setHeader = jest.fn();
  res.send = jest.fn(() => res);
  res.status = jest.fn(() => res);
  return res;
};
const next = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  exportUtils.buildExportRows.mockResolvedValue({ entries: [{ entryId: 'a' }], lines: [], truncated: false });
});

describe('transactionController.exportTransactions()', () => {
  const req = (query) => ({ query, user: { businessId: 'biz1', id: 'u1' } });

  it('defaults to xlsx and sends a spreadsheet', async () => {
    const res = mockRes();
    await transactionController.exportTransactions(req({}), res, next);

    expect(exportUtils.toXlsx).toHaveBeenCalled();
    expect(res.setHeader).toHaveBeenCalledWith(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    expect(res.send).toHaveBeenCalledWith(Buffer.from('XLSX_BODY'));
  });

  it('sends CSV when asked', async () => {
    const res = mockRes();
    await transactionController.exportTransactions(req({ format: 'csv' }), res, next);

    expect(exportUtils.toCsv).toHaveBeenCalled();
    expect(res.setHeader).toHaveBeenCalledWith('Content-Type', 'text/csv; charset=utf-8');
    expect(res.send).toHaveBeenCalledWith('CSV_BODY');
  });

  it('names the file with the business and date range', async () => {
    const res = mockRes();
    await transactionController.exportTransactions(req({ format: 'csv', startDate: '2026-01-01', endDate: '2026-01-31' }), res, next);

    const disp = res.setHeader.mock.calls.find((c) => c[0] === 'Content-Disposition')[1];
    expect(disp).toContain('2026-01-01');
    expect(disp).toContain('2026-01-31');
    expect(disp).toContain('.csv');
  });

  it('scopes the export to the caller business', async () => {
    await transactionController.exportTransactions(req({}), mockRes(), next);
    expect(exportUtils.buildExportRows).toHaveBeenCalledWith('biz1', expect.any(Object));
  });

  it('refuses instead of silently truncating when the result is too large', async () => {
    exportUtils.buildExportRows.mockResolvedValue({ entries: [], lines: [], truncated: true });
    await transactionController.exportTransactions(req({}), mockRes(), next);

    expect(next).toHaveBeenCalledWith(expect.objectContaining({ statusCode: 413 }));
    expect(exportUtils.toXlsx).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/controllers/transaction.export.test.js 2>&1 | tail -15
```

Expected: FAIL — `transactionController.exportTransactions is not a function`.

- [ ] **Step 3: Implement**

Add to `validations/transaction.validation.js` after `transactionFiltersSchema` (line 286):

```js
/**
 * Export filters = the list's filters, minus paging, plus a format.
 * Reusing the list schema is deliberate: what the screen shows is exactly what
 * the file contains.
 */
const transactionExportSchema = transactionFiltersSchema
  .keys({
    format: Joi.string().valid('csv', 'xlsx').default('xlsx'),
    page: Joi.forbidden(),
    limit: Joi.forbidden(),
  });
```

Add `transactionExportSchema,` to the exports at line 312.

Add to `controllers/transaction.controller.js` near `getTransactions` (after line 1087):

```js
/**
 * Export transactions to a spreadsheet.
 * GET /api/v1/transactions/export?format=csv|xlsx&<same filters as the list>
 */
const exportTransactions = async (req, res, next) => {
  try {
    const { format = 'xlsx', ...filters } = req.query;
    const { entries, lines, truncated } = await exportUtils.buildExportRows(
      req.user.businessId,
      filters
    );

    if (truncated) {
      throw new ApiError(
        413,
        `That's more than ${exportUtils.EXPORT_ROW_CAP.toLocaleString()} transactions. `
        + 'Pick a shorter date range and try again.'
      );
    }

    const period = filters.startDate || filters.endDate
      ? `${filters.startDate || 'start'}_to_${filters.endDate || 'today'}`
      : 'all';
    const business = await businessService.getBusinessById(req.user.businessId).catch(() => null);
    const safeName = String(business?.businessName || 'vousfin').replace(/[^a-z0-9]+/gi, '-').toLowerCase();
    const base = `${safeName}-transactions-${period}`;

    if (format === 'csv') {
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${base}.csv"`);
      return res.send(exportUtils.toCsv(entries));
    }

    const buffer = await exportUtils.toXlsx({
      entries,
      lines,
      meta: {
        businessName: business?.businessName || '',
        baseCurrency: business?.currency || '',
        period: period === 'all' ? 'All dates' : period.replace('_to_', ' to '),
      },
    });
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${base}.xlsx"`);
    return res.send(buffer);
  } catch (error) {
    next(error);
  }
};
```

Add the requires at the top of the controller, next to the existing ones:

```js
const exportUtils = require('../utils/transactionExport.utils');
const businessService = require('../services/business.service');
```

(If `businessService` is already required in this file, do not add it twice.)

Add `exportTransactions,` to the exports block at line 1443.

Add the route in `routes/v1/transaction.routes.js` **immediately before** line 77 (`router.get('/'...)`) — it must be declared before `/:id` or Express will treat `export` as an id:

```js
// ── Export ────────────────────────────────────────────────────────────────────
router.get('/export', validate(transactionExportSchema, 'query'), transactionController.exportTransactions);
```

Import `transactionExportSchema` alongside the other schemas at the top of the routes file.

- [ ] **Step 4: Run the tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/controllers/transaction.export.test.js tests/unit/utils/transactionExport.utils.test.js 2>&1 | tail -15
```

Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add controllers/transaction.controller.js validations/transaction.validation.js routes/v1/transaction.routes.js tests/unit/controllers/transaction.export.test.js && git commit -m "feat(export): GET /transactions/export (csv + xlsx)"
```

## Task 2.4: Export button on the transactions page

**Files:**
- Create: `vousfin-frontend-main/src/components/transactions/ExportTransactionsButton.jsx`
- Create: `vousfin-frontend-main/src/components/transactions/ExportTransactionsButton.test.jsx`
- Modify: `vousfin-frontend-main/src/services/transaction.service.js` (add `exportTransactions`)
- Modify: `vousfin-frontend-main/src/pages/transactions/TransactionsList.jsx:199+` (render the button in the header)

**Interfaces:**
- Consumes: `GET /transactions/export` (Task 2.3).
- Produces: `<ExportTransactionsButton filters={obj} />`.

- [ ] **Step 1: Write the failing test**

Create `src/components/transactions/ExportTransactionsButton.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ExportTransactionsButton from './ExportTransactionsButton'
import transactionService from '@/services/transaction.service'

vi.mock('@/services/transaction.service', () => ({
  default: { exportTransactions: vi.fn(async () => ({ data: new Blob(['x']) })) },
}))

beforeEach(() => {
  vi.clearAllMocks()
  global.URL.createObjectURL = vi.fn(() => 'blob:url')
  global.URL.revokeObjectURL = vi.fn()
})

describe('ExportTransactionsButton', () => {
  it('opens the options when clicked', () => {
    render(<ExportTransactionsButton filters={{}} />)
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
    expect(screen.getByText(/excel/i)).toBeInTheDocument()
    expect(screen.getByText(/csv/i)).toBeInTheDocument()
  })

  it('passes the current filters through to the server', async () => {
    render(<ExportTransactionsButton filters={{ startDate: '2026-07-01', transactionType: 'Expense' }} />)
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
    fireEvent.click(screen.getByText(/excel/i))

    await waitFor(() => expect(transactionService.exportTransactions).toHaveBeenCalled())
    expect(transactionService.exportTransactions).toHaveBeenCalledWith(
      expect.objectContaining({ startDate: '2026-07-01', transactionType: 'Expense', format: 'xlsx' })
    )
  })

  it('requests csv when csv is chosen', async () => {
    render(<ExportTransactionsButton filters={{}} />)
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
    fireEvent.click(screen.getByText(/csv/i))

    await waitFor(() => expect(transactionService.exportTransactions).toHaveBeenCalledWith(
      expect.objectContaining({ format: 'csv' })
    ))
  })
})
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-frontend-main && npx vitest run src/components/transactions/ExportTransactionsButton.test.jsx --reporter=json --outputFile=/tmp/vitest-exp.json 2>&1 | tail -15
```

Expected: FAIL — cannot resolve the component.

- [ ] **Step 3: Implement**

Add to `src/services/transaction.service.js`:

```js
  exportTransactions: (params = {}) =>
    api.get('/transactions/export', { params, responseType: 'blob' }),
```

Create `src/components/transactions/ExportTransactionsButton.jsx`:

```jsx
import { useState } from 'react'
import { Download, FileSpreadsheet, FileText } from 'lucide-react'
import toast from 'react-hot-toast'
import transactionService from '@/services/transaction.service'
import { getErrorMessage } from '@/utils/errorHandler'

/**
 * Downloads everything matching the CURRENT filters — not just the rows on
 * screen. The work happens on the server, so a full year exports fine.
 */
export default function ExportTransactionsButton({ filters = {} }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const run = async (format) => {
    setOpen(false)
    setBusy(true)
    try {
      const clean = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== '')
      )
      const res = await transactionService.exportTransactions({ ...clean, format })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `transactions.${format === 'csv' ? 'csv' : 'xlsx'}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Your file is downloading')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={busy}
        className="flex items-center gap-2 rounded-lg border border-glass px-3 py-2 text-small text-text-primary transition-colors hover:bg-glass-hover disabled:opacity-50"
      >
        <Download className="h-4 w-4" />
        {busy ? 'Preparing…' : 'Export'}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-glass bg-charcoal p-1 shadow-lg">
          <button
            onClick={() => run('xlsx')}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-small hover:bg-glass-hover"
          >
            <FileSpreadsheet className="h-4 w-4 text-positive" />
            <span>
              Excel file
              <span className="block text-label text-text-muted">Includes full account detail</span>
            </span>
          </button>
          <button
            onClick={() => run('csv')}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-small hover:bg-glass-hover"
          >
            <FileText className="h-4 w-4 text-accent" />
            <span>
              CSV file
              <span className="block text-label text-text-muted">For other software</span>
            </span>
          </button>
          <p className="px-3 py-2 text-label text-text-muted">
            Exports everything matching your current filters.
          </p>
        </div>
      )}
    </div>
  )
}
```

Render it in `TransactionsList.jsx` next to the existing page-header actions, passing the page's live filter state:

```jsx
<ExportTransactionsButton filters={filters} />
```

Read the component's existing filter state variable name at the top of `TransactionsList.jsx` and pass exactly that object. Import at the top:

```jsx
import ExportTransactionsButton from '@/components/transactions/ExportTransactionsButton'
```

- [ ] **Step 4: Run tests + build**

```bash
cd vousfin-frontend-main && npx vitest run --reporter=json --outputFile=/tmp/vitest-all.json 2>&1 | tail -5 && node -e "const r=require('/tmp/vitest-all.json');console.log('failed',r.numFailedTests)" && npm run build 2>&1 | tail -5
```

Expected: `failed 0`, build clean.

- [ ] **Step 5: Commit**

```bash
cd vousfin-frontend-main && git add src/components/transactions/ src/services/transaction.service.js src/pages/transactions/TransactionsList.jsx && git commit -m "feat(export): export button on transactions list"
```

- [ ] **Step 6: Live-verify**

With the dev server running, open Transactions, set a date range, export xlsx, and open the downloaded file. Confirm: Sheet 1 has your columns; Sheet 2's TOTAL row shows debits equal to credits; any payroll/tax entry shows `-- Split --` on Sheet 1 and its full lines on Sheet 2.

---

**Phase 2 checkpoint.** Export works end to end. Backend suite green, frontend green, build clean. Stop and report before Phase 3.

---

# Phase 3 — Money you lent out

Touches the ledger. `scripts/ledgerDrift.js` must read 0 at the end.

## Task 3.1: Constants, control account and party kind

**Files:**
- Modify: `vousfin-backend-main/config/constants.js:141` (add account 1145), `:365` (add types), `:295` (NON_TAXABLE_TYPES)
- Modify: `vousfin-backend-main/models/Customer.model.js:81` (add `partyKind`, `currentLoanBalance`)
- Test: `vousfin-backend-main/tests/unit/config/loanConstants.test.js`

**Interfaces:**
- Produces: `TRANSACTION_TYPES.LOAN_ISSUED = 'Money Lent'`; `TRANSACTION_TYPES.LOAN_REPAYMENT_RECEIVED = 'Loan Repayment Received'`; `LOAN_CONTROL_CODES = { DEFAULT: '1145', EMPLOYEE: '1165' }`; `Customer.partyKind`; `Customer.currentLoanBalance`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/config/loanConstants.test.js`:

```js
'use strict';
const { TRANSACTION_TYPES, DEFAULT_ACCOUNTS, LOAN_CONTROL_CODES } = require('../../../config/constants');
const Customer = require('../../../models/Customer.model');

describe('loan constants', () => {
  it('has a type for money lent out, distinct from money borrowed', () => {
    expect(TRANSACTION_TYPES.LOAN_ISSUED).toBe('Money Lent');
    expect(TRANSACTION_TYPES.LOAN_DISBURSEMENT).toBe('Loan Disbursement');
    expect(TRANSACTION_TYPES.LOAN_ISSUED).not.toBe(TRANSACTION_TYPES.LOAN_DISBURSEMENT);
  });

  it('has a type for being paid back, distinct from us repaying a bank', () => {
    expect(TRANSACTION_TYPES.LOAN_REPAYMENT_RECEIVED).toBe('Loan Repayment Received');
    expect(TRANSACTION_TYPES.LOAN_REPAYMENT).toBe('Loan Repayment');
  });

  it('ships 1145 as a default asset account', () => {
    const acc = DEFAULT_ACCOUNTS.find((a) => a.accountCode === '1145');
    expect(acc).toBeDefined();
    expect(acc.accountType).toBe('Asset');
    expect(acc.normalBalance).toBe('Debit');
    expect(acc.accountSubtype).toBe('Current Assets');
  });

  it('keeps every default account code unique', () => {
    const codes = DEFAULT_ACCOUNTS.map((a) => a.accountCode);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it('names both loan control accounts', () => {
    expect(LOAN_CONTROL_CODES.DEFAULT).toBe('1145');
    expect(LOAN_CONTROL_CODES.EMPLOYEE).toBe('1165');
  });
});

describe('Customer party fields', () => {
  it('defaults partyKind to customer so existing records are unchanged', () => {
    const c = new Customer({ businessId: '507f1f77bcf86cd799439011', fullName: 'Ali' });
    expect(c.partyKind).toBe('customer');
  });

  it('tracks loan balance separately from trade receivable balance', () => {
    const c = new Customer({ businessId: '507f1f77bcf86cd799439011', fullName: 'Ali' });
    expect(c.currentLoanBalance).toBe(0);
    expect(c.currentReceivableBalance).toBe(0);
    expect(Customer.schema.path('currentLoanBalance')).toBeDefined();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/config/loanConstants.test.js 2>&1 | tail -15
```

Expected: FAIL — `TRANSACTION_TYPES.LOAN_ISSUED` is undefined.

- [ ] **Step 3: Implement**

In `config/constants.js`, add the account after line 141 (`1140 Other Receivables`):

```js
    { accountCode: '1145', accountName: 'Loans & Advances to Others',  accountType: 'Asset',     accountSubtype: 'Current Assets',          normalBalance: 'Debit',  isDefault: true },
```

Add the types in the Financing & Capital block after line 366:

```js
    // Money we lent OUT. Deliberately separate from LOAN_DISBURSEMENT, which is
    // money we BORROWED (it credits a liability). Lending creates an asset.
    LOAN_ISSUED:             'Money Lent',
    LOAN_REPAYMENT_RECEIVED: 'Loan Repayment Received',
```

Add a top-level constant next to `DEFAULT_ACCOUNTS`:

```js
  /**
   * Control accounts for the loans-receivable sub-ledger. Loans must never post
   * to 1110 (Accounts Receivable): trade receivables and loans are different
   * balance-sheet lines, and the VE-5/6 reconcile compares 1110 against the
   * trade open-items total. A loan in that pot drifts it permanently.
   */
  LOAN_CONTROL_CODES: { DEFAULT: '1145', EMPLOYEE: '1165' },
```

Add both new types to `NON_TAXABLE_TYPES` in `services/transaction.service.js:295` (lending money is not a supply):

```js
      TRANSACTION_TYPES.LOAN_ISSUED,
      TRANSACTION_TYPES.LOAN_REPAYMENT_RECEIVED,
```

In `models/Customer.model.js`, add after `isActive` (line 84):

```js
    /**
     * What this party is to the business. Defaults to 'customer' so every
     * existing record and query behaves exactly as before.
     */
    partyKind: {
      type: String,
      enum: ['customer', 'employee', 'individual', 'other'],
      default: 'customer',
      index: true,
    },
    /**
     * Non-trade money this party owes us (loans and advances).
     * SEPARATE from currentReceivableBalance on purpose: that field drives the
     * credit-limit check and getTopDebtors. Folding loans into it would block
     * sales against a limit consumed by an unrelated personal loan.
     */
    currentLoanBalance: {
      type: Number,
      default: 0,
      min: 0,
    },
```

- [ ] **Step 4: Run the test plus the account-defaults suite**

```bash
cd vousfin-backend-main && npx jest tests/unit/config/loanConstants.test.js -t "" 2>&1 | tail -10 && npx jest --testPathPattern "account" 2>&1 | tail -10
```

Expected: PASS. The uniqueness test and any existing DEFAULT_ACCOUNTS count assertion must be green — if a test asserts "78 accounts", update it to 79 as part of this task.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add config/constants.js models/Customer.model.js services/transaction.service.js tests/unit/config/loanConstants.test.js && git commit -m "feat(loans): loan transaction types, control account 1145, party kind"
```

## Task 3.2: Loan open items in the authority layer

**Files:**
- Modify: `vousfin-backend-main/repositories/transaction.repository.js` (add `getOutstandingLoans`)
- Modify: `vousfin-backend-main/services/openItem.service.js:177-243` (`resolveOpenItem`), `:246-256` (`_sideCfg`), `:336-347` (`openItems`), `:357-416` (`sumOpenLedger`)
- Test: `vousfin-backend-main/tests/unit/services/openItem.loans.test.js`

**Interfaces:**
- Consumes: `TRANSACTION_TYPES.LOAN_ISSUED` (Task 3.1).
- Produces: `transactionRepository.getOutstandingLoans(businessId) → Promise<Array>`; `openItemService.openItems(businessId, 'loan')`; `openItemService.sumOpenLedger(businessId, 'loan', { byControlAccount: true }) → { byAccount: { '1145': n, '1165': n }, total: n }`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/openItem.loans.test.js`:

```js
'use strict';
const mongoose = require('mongoose');
const { TRANSACTION_TYPES } = require('../../../config/constants');

jest.mock('../../../repositories/transaction.repository', () => ({
  getOutstandingReceivables: jest.fn(async () => []),
  getOutstandingPayables: jest.fn(async () => []),
  getOutstandingLoans: jest.fn(async () => []),
}));

const transactionRepository = require('../../../repositories/transaction.repository');
const openItem = require('../../../services/openItem.service');
const JournalEntry = require('../../../models/JournalEntry.model');

const BIZ = new mongoose.Types.ObjectId().toString();

const loanJe = {
  _id: 'je-loan',
  businessId: BIZ,
  transactionType: TRANSACTION_TYPES.LOAN_ISSUED,
  remainingBalance: 1250,
  partiallyPaidAmount: 0,
  amount: 1250,
  customerId: 'party1',
  isProjection: false,
  exchangeRate: 1,
};

describe('openItem — loan direction', () => {
  afterEach(() => jest.restoreAllMocks());

  it('resolves a Money Lent entry as a loan open item', async () => {
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({
      session: () => ({ lean: async () => loanJe }),
      lean: async () => loanJe,
    });

    const item = await openItem.resolveOpenItem(BIZ, { journalEntryId: 'je-loan' });

    expect(item.direction).toBe('loan');
    expect(item.authority).toBe('journal');
    expect(item.partyId).toBe('party1');
    expect(item.remainingBase).toBe(1250);
  });

  it('refuses a loan that claims to be a document projection', async () => {
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({
      session: () => ({ lean: async () => ({ ...loanJe, isProjection: true }) }),
      lean: async () => ({ ...loanJe, isProjection: true }),
    });

    await expect(openItem.resolveOpenItem(BIZ, { journalEntryId: 'je-loan' }))
      .rejects.toMatchObject({ statusCode: 400 });
  });

  it('openItems("loan") reads only the loan query, never the AR query', async () => {
    transactionRepository.getOutstandingLoans.mockResolvedValue([
      { _id: 'je-loan', transactionDate: new Date('2026-07-20'), remainingBalance: 1250 },
    ]);

    const rows = await openItem.openItems(BIZ, 'loan');

    expect(transactionRepository.getOutstandingLoans).toHaveBeenCalledWith(BIZ);
    expect(transactionRepository.getOutstandingReceivables).not.toHaveBeenCalled();
    expect(rows).toHaveLength(1);
  });

  it('a loan never appears in the receivable union', async () => {
    transactionRepository.getOutstandingReceivables.mockResolvedValue([]);
    jest.spyOn(openItem, 'documentOpenItems').mockResolvedValue([]);

    const rows = await openItem.openItems(BIZ, 'receivable');

    expect(rows).toHaveLength(0);
    expect(transactionRepository.getOutstandingLoans).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/openItem.loans.test.js 2>&1 | tail -15
```

Expected: FAIL — `resolveOpenItem` throws "Allocations must target a credit sale…".

- [ ] **Step 3: Implement**

Add to `repositories/transaction.repository.js`, next to `getOutstandingReceivables` (line 421):

```js
  /**
   * Open loan items — money the business lent out and has not been paid back.
   * Journal-authority only: a loan has no invoice document, so unlike AR there
   * is no document side to union in.
   */
  async getOutstandingLoans(businessId) {
    const validBusinessId = sanitizeAndValidateId(businessId);
    return this.model.find({
      businessId: validBusinessId,
      transactionType: TRANSACTION_TYPES.LOAN_ISSUED,
      paymentStatus: { $in: [PAYMENT_STATUS.UNPAID, PAYMENT_STATUS.PARTIALLY_PAID, PAYMENT_STATUS.OVERDUE] },
      remainingBalance: { $gt: 0 },
      isProjection: { $ne: true },
      isArchived: { $ne: true },
    })
      .populate('customerId', 'fullName businessName partyKind')
      .populate('debitAccountId', 'accountCode accountName')
      .populate('creditAccountId', 'accountCode accountName')
      .sort({ transactionDate: -1 })
      .lean();
  }
```

In `services/openItem.service.js`, replace the direction detection in `resolveOpenItem` (lines 177-183):

```js
  const isAR = je.transactionType === TRANSACTION_TYPES.CREDIT_SALE;
  const isAP = je.transactionType === TRANSACTION_TYPES.CREDIT_PURCHASE;
  const isLoan = je.transactionType === TRANSACTION_TYPES.LOAN_ISSUED;
  if (!isAR && !isAP && !isLoan) {
    throw new ApiError(400, 'Allocations must target a credit sale (invoice), a credit purchase (bill), or a loan');
  }
  // A loan has no source document, so a "projection loan" is a contradiction —
  // refuse it rather than resolve it against a document that cannot exist.
  if (isLoan && je.isProjection === true) {
    throw new ApiError(400, 'A loan entry cannot be a document projection — this entry is corrupt.');
  }
  const direction = isLoan ? 'loan' : isAR ? 'receivable' : 'payable';
  const partyType = isLoan ? 'party' : isAR ? 'customer' : 'vendor';
```

Then in the journal-authority return block (line 234), make `partyId` loan-aware:

```js
    partyId: (isAR || isLoan ? je.customerId : je.vendorId) || null,
```

Add a `loan` branch to `_sideCfg` (line 246):

```js
function _sideCfg(direction) {
  if (direction === 'loan') {
    return {
      isAR: false,
      isLoan: true,
      Model: null,          // loans have no document side
      anchor: null,
      states: [],
      partyField: 'customerId',
      txType: TRANSACTION_TYPES.LOAN_ISSUED,
    };
  }
  const isAR = direction === 'receivable';
  return {
    isAR,
    isLoan: false,
    Model: isAR ? require('../models/Invoice.model') : require('../models/Bill.model'),
    anchor: isAR ? 'arJournalId' : 'apLiabilityJournalId',
    states: isAR ? OPEN_INVOICE_STATES : OPEN_BILL_STATES,
    partyField: isAR ? 'customerId' : 'vendorId',
    txType: isAR ? TRANSACTION_TYPES.CREDIT_SALE : TRANSACTION_TYPES.CREDIT_PURCHASE,
  };
}
```

Replace `openItems` (line 336):

```js
async function openItems(businessId, direction) {
  const transactionRepository = require('../repositories/transaction.repository');

  // Loans are journal-authority only — no document side to union in.
  if (direction === 'loan') {
    return transactionRepository.getOutstandingLoans(businessId);
  }

  const [jeRows, docRows] = await Promise.all([
    direction === 'receivable'
      ? transactionRepository.getOutstandingReceivables(businessId)
      : transactionRepository.getOutstandingPayables(businessId),
    documentOpenItems(businessId, direction),
  ]);
  return [...jeRows, ...docRows].sort(
    (a, b) => new Date(b.transactionDate) - new Date(a.transactionDate)
  );
}
```

Add a loan branch at the top of `sumOpenLedger` (line 357), before the existing body:

```js
  if (direction === 'loan') {
    const mongooseL = require('mongoose');
    const JournalEntryL = require('../models/JournalEntry.model');
    const bidL = new mongooseL.Types.ObjectId(String(businessId));
    const matchL = {
      businessId: bidL,
      transactionType: TRANSACTION_TYPES.LOAN_ISSUED,
      status: { $in: OPEN_JE_STATUSES },
      isProjection: { $ne: true },
    };
    if (partyLinkedOnly) matchL.customerId = { $ne: null };

    // Grouped by the DEBIT account, because 1145 and 1165 are separate control
    // accounts that must each reconcile on their own.
    const agg = await JournalEntryL.aggregate([
      { $match: matchL },
      { $lookup: { from: 'chartofaccounts', localField: 'debitAccountId', foreignField: '_id',
                   as: 'acc', pipeline: [{ $project: { accountCode: 1 } }] } },
      { $unwind: { path: '$acc', preserveNullAndEmptyArrays: true } },
      { $group: { _id: '$acc.accountCode', sum: { $sum: '$remainingBalance' } } },
    ]);
    const byAccount = {};
    let total = 0;
    for (const row of agg) {
      byAccount[row._id || 'unknown'] = r2(row.sum);
      total = r2(total + row.sum);
    }
    return { byAccount, total };
  }
```

Add `TRANSACTION_TYPES.LOAN_ISSUED` usage — it is already destructured at line 29. Confirm `TRANSACTION_TYPES` includes the new keys (Task 3.1).

- [ ] **Step 4: Run the tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/openItem 2>&1 | tail -15
```

Expected: PASS — the new loan file **and** every existing `openItem` test still green. Existing AR/AP behaviour must be byte-identical.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add repositories/transaction.repository.js services/openItem.service.js tests/unit/services/openItem.loans.test.js && git commit -m "feat(loans): third 'loan' direction in the open-item authority"
```

## Task 3.3: Lend money, get paid back

**Files:**
- Modify: `vousfin-backend-main/services/transaction.service.js` (add `issueLoan`; extend `getOutstandingBalances` at `:1788`)
- Modify: `vousfin-backend-main/controllers/transaction.controller.js` (add `issueLoan`; allow `loan` in `getOutstandingBalances` at `:169`)
- Modify: `vousfin-backend-main/routes/v1/transaction.routes.js` (add `POST /loan`)
- Modify: `vousfin-backend-main/validations/transaction.validation.js` (add `issueLoanSchema`)
- Test: `vousfin-backend-main/tests/unit/services/transaction.loans.test.js`

**Interfaces:**
- Consumes: Tasks 3.1, 3.2; `transaction.service.createTransaction`; `transaction.service.recordPartialPayment`.
- Produces: `transactionService.issueLoan(businessId, payload, userId, ip) → Promise<JournalEntry>` where payload is `{ amount, partyId?, partyName?, partyKind?, fromAccountId, transactionDate?, dueDate?, description? }`; `POST /api/v1/transactions/loan`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/transaction.loans.test.js`:

```js
'use strict';
const mongoose = require('mongoose');
const { TRANSACTION_TYPES, LOAN_CONTROL_CODES } = require('../../../config/constants');

jest.mock('../../../services/transaction.service', () => {
  const actual = jest.requireActual('../../../services/transaction.service');
  return actual;
});

const transactionService = require('../../../services/transaction.service');
const Customer = require('../../../models/Customer.model');
const accountRepository = require('../../../repositories/account.repository');

const BIZ = new mongoose.Types.ObjectId().toString();
const CASH = new mongoose.Types.ObjectId().toString();
const LOAN_ACC = new mongoose.Types.ObjectId().toString();

describe('transactionService.issueLoan()', () => {
  let createSpy;

  beforeEach(() => {
    jest.restoreAllMocks();
    createSpy = jest.spyOn(transactionService, 'createTransaction')
      .mockResolvedValue({ _id: 'je1', amount: 1250 });
    jest.spyOn(accountRepository, 'findByCode')
      .mockResolvedValue({ _id: LOAN_ACC, accountCode: '1145', accountName: 'Loans & Advances to Others' });
  });

  it('debits the loan control account and credits the money source', async () => {
    jest.spyOn(Customer, 'findOne').mockResolvedValue({ _id: 'p1', fullName: 'Ali Raza', partyKind: 'individual' });

    await transactionService.issueLoan(BIZ, {
      amount: 1250, partyId: 'p1', fromAccountId: CASH,
    }, 'u1', '127.0.0.1');

    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        businessId: BIZ,
        amount: 1250,
        debitAccountId: LOAN_ACC,
        creditAccountId: CASH,
        transactionType: TRANSACTION_TYPES.LOAN_ISSUED,
        customerId: 'p1',
        remainingBalance: 1250,
      }),
      'u1', '127.0.0.1'
    );
  });

  it('routes an employee loan to 1165, not 1145', async () => {
    jest.spyOn(Customer, 'findOne').mockResolvedValue({ _id: 'p2', fullName: 'Sara', partyKind: 'employee' });
    const codeSpy = jest.spyOn(accountRepository, 'findByCode')
      .mockResolvedValue({ _id: 'emp-acc', accountCode: '1165' });

    await transactionService.issueLoan(BIZ, { amount: 500, partyId: 'p2', fromAccountId: CASH }, 'u1', '1.1.1.1');

    expect(codeSpy).toHaveBeenCalledWith(BIZ, LOAN_CONTROL_CODES.EMPLOYEE);
  });

  it('creates the person when only a name is given', async () => {
    jest.spyOn(Customer, 'findOne').mockResolvedValue(null);
    const createParty = jest.spyOn(Customer, 'create')
      .mockResolvedValue({ _id: 'new1', fullName: 'Ali Raza', partyKind: 'individual' });

    await transactionService.issueLoan(BIZ, {
      amount: 1250, partyName: 'Ali Raza', partyKind: 'individual', fromAccountId: CASH,
    }, 'u1', '1.1.1.1');

    expect(createParty).toHaveBeenCalledWith(expect.objectContaining({
      businessId: BIZ, fullName: 'Ali Raza', partyKind: 'individual',
    }));
    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ customerId: 'new1' }), 'u1', '1.1.1.1'
    );
  });

  it('refuses without a person — an untracked loan is the bug we are fixing', async () => {
    await expect(transactionService.issueLoan(BIZ, { amount: 1250, fromAccountId: CASH }, 'u1', '1.1.1.1'))
      .rejects.toMatchObject({ statusCode: 400 });
  });

  it('refuses a zero or negative amount', async () => {
    jest.spyOn(Customer, 'findOne').mockResolvedValue({ _id: 'p1', partyKind: 'individual' });
    await expect(transactionService.issueLoan(BIZ, { amount: 0, partyId: 'p1', fromAccountId: CASH }, 'u1', '1.1.1.1'))
      .rejects.toMatchObject({ statusCode: 400 });
  });

  it('moves the loan balance, never the trade receivable balance', async () => {
    jest.spyOn(Customer, 'findOne').mockResolvedValue({ _id: 'p1', partyKind: 'individual' });
    const upd = jest.spyOn(Customer, 'updateOne').mockResolvedValue({});

    await transactionService.issueLoan(BIZ, { amount: 1250, partyId: 'p1', fromAccountId: CASH }, 'u1', '1.1.1.1');

    const update = upd.mock.calls[0][1];
    expect(update.$inc).toHaveProperty('currentLoanBalance', 1250);
    expect(update.$inc).not.toHaveProperty('currentReceivableBalance');
  });
});

describe('transactionService.getOutstandingBalances()', () => {
  it('accepts loan as a valid type', async () => {
    jest.spyOn(require('../../../services/openItem.service'), 'openItems').mockResolvedValue([]);
    await expect(transactionService.getOutstandingBalances(BIZ, 'loan')).resolves.toEqual([]);
  });

  it('still refuses nonsense types', async () => {
    await expect(transactionService.getOutstandingBalances(BIZ, 'nope'))
      .rejects.toMatchObject({ statusCode: 400 });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/transaction.loans.test.js 2>&1 | tail -15
```

Expected: FAIL — `transactionService.issueLoan is not a function`.

- [ ] **Step 3: Implement**

Add to `services/transaction.service.js`, near `getOutstandingBalances`:

```js
  /**
   * Lend money to a person.
   *
   *   DR  Loans & Advances (1145, or 1165 for an employee)
   *   CR  the bank/cash account the money left from
   *
   * The entry carries the party and its own open balance, so it shows up under
   * "Loans & advances" and is settled by the SAME payment engine as an invoice.
   * It deliberately does NOT touch 1110 Accounts Receivable — a loan is not a
   * trade receivable, and mixing them drifts the AR reconcile.
   */
  async issueLoan(businessId, payload, userId, ipAddress) {
    const {
      amount, partyId, partyName, partyKind = 'individual',
      fromAccountId, transactionDate, dueDate, description,
    } = payload;

    const amt = Number(amount);
    if (!Number.isFinite(amt) || amt <= 0) {
      throw new ApiError(400, 'Enter how much you lent — it must be more than zero.');
    }
    if (!fromAccountId) {
      throw new ApiError(400, 'Choose which account the money came from.');
    }

    const Customer = require('../models/Customer.model');
    let party = null;
    if (partyId) {
      party = await Customer.findOne({ _id: partyId, businessId });
      if (!party) throw new ApiError(404, 'That person was not found.');
    } else if (partyName && String(partyName).trim()) {
      party = await Customer.create({
        businessId,
        fullName: String(partyName).trim(),
        partyKind,
        isActive: true,
      });
    } else {
      throw new ApiError(400, 'Tell us who you lent the money to, so we can track what they owe you.');
    }

    const controlCode = party.partyKind === 'employee'
      ? LOAN_CONTROL_CODES.EMPLOYEE
      : LOAN_CONTROL_CODES.DEFAULT;
    const loanAccount = await accountRepository.findByCode(businessId, controlCode);
    if (!loanAccount) {
      throw new ApiError(500, 'The loans account is missing from your chart of accounts. Open Accounts once to restore it, then try again.');
    }

    const entry = await this.createTransaction({
      businessId,
      transactionDate: transactionDate || new Date(),
      description: description || `Loan to ${party.fullName}`,
      transactionType: TRANSACTION_TYPES.LOAN_ISSUED,
      amount: amt,
      debitAccountId: loanAccount._id,
      creditAccountId: fromAccountId,
      customerId: party._id,
      remainingBalance: amt,
      partiallyPaidAmount: 0,
      paymentStatus: PAYMENT_STATUS.UNPAID,
      dueDate: dueDate || null,
      createdBy: userId,
      inputMethod: 'manual',
    }, userId, ipAddress);

    // Loan balance only. currentReceivableBalance drives credit limits and
    // top-debtors — a personal loan must never consume a sales credit limit.
    await Customer.updateOne(
      { _id: party._id, businessId },
      { $inc: { currentLoanBalance: amt } }
    );

    return entry;
  }
```

Ensure `LOAN_CONTROL_CODES` and `accountRepository` are imported at the top of the service (both patterns already exist there — add `LOAN_CONTROL_CODES` to the `require('../config/constants')` destructure).

Widen `getOutstandingBalances` (line 1788):

```js
  async getOutstandingBalances(businessId, type) {
    if (!['receivable', 'payable', 'loan'].includes(type)) {
      throw new ApiError(400, 'Invalid outstanding balance type. Use "receivable", "payable" or "loan"');
    }
    return require('./openItem.service').openItems(businessId, type);
  }
```

Widen the controller guard at `controllers/transaction.controller.js:170`:

```js
    if (!type) throw new ApiError(400, 'type query parameter is required (receivable, payable or loan)');
```

Add the controller action next to `getOutstandingBalances`:

```js
/**
 * Lend money to a person.
 * POST /api/v1/transactions/loan
 */
const issueLoan = async (req, res, next) => {
  try {
    const entry = await transactionService.issueLoan(
      req.user.businessId, req.body, req.user.id, req.ip
    );
    ApiResponse.created(res, entry, 'Loan recorded');
  } catch (error) {
    next(error);
  }
};
```

Export it, and add the validation schema:

```js
const issueLoanSchema = Joi.object({
  amount: Joi.number().positive().required(),
  partyId: Joi.string().pattern(objectIdPattern).optional(),
  partyName: Joi.string().max(100).optional(),
  partyKind: Joi.string().valid('customer', 'employee', 'individual', 'other').default('individual'),
  fromAccountId: Joi.string().pattern(objectIdPattern).required(),
  transactionDate: Joi.date().iso().optional(),
  dueDate: Joi.date().iso().optional().allow(null),
  description: Joi.string().max(500).optional().allow(''),
}).or('partyId', 'partyName');
```

Add the route in `routes/v1/transaction.routes.js`, next to `/payment` (line 42):

```js
router.post('/loan', validate(issueLoanSchema), transactionController.issueLoan);
```

- [ ] **Step 4: Run the tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/transaction.loans.test.js 2>&1 | tail -15
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add services/transaction.service.js controllers/transaction.controller.js routes/v1/transaction.routes.js validations/transaction.validation.js tests/unit/services/transaction.loans.test.js && git commit -m "feat(loans): issueLoan — posts to the loan sub-ledger with a real counterparty"
```

## Task 3.4: The VE-7 loan invariant

**Files:**
- Modify: `vousfin-backend-main/services/ledgerIntegrity.service.js:149-196` (add `computeLoanSubledgerDrift`, export it)
- Modify: `vousfin-backend-main/services/booksAssurance.service.js` (add the check)
- Test: `vousfin-backend-main/tests/unit/services/ledgerIntegrity.loans.test.js`

**Interfaces:**
- Consumes: `openItemService.sumOpenLedger(businessId, 'loan', …)` (Task 3.2); `computeDrift` (existing).
- Produces: `ledgerIntegrity.computeLoanSubledgerDrift(businessId) → { accounts: [{ code, controlDerived, openItems, drift, reconciled }], reconciled: boolean }`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/ledgerIntegrity.loans.test.js`:

```js
'use strict';
const ledgerIntegrity = require('../../../services/ledgerIntegrity.service');
const openItemService = require('../../../services/openItem.service');

const BIZ = '507f1f77bcf86cd799439011';

describe('computeLoanSubledgerDrift()', () => {
  afterEach(() => jest.restoreAllMocks());

  const withBalances = (accounts) =>
    jest.spyOn(ledgerIntegrity, 'computeDrift').mockResolvedValue({ accounts });

  it('reconciles when the control account matches the open loans', async () => {
    withBalances([{ code: '1145', derived: 1250 }, { code: '1165', derived: 0 }]);
    jest.spyOn(openItemService, 'sumOpenLedger').mockResolvedValue({
      byAccount: { 1145: 1250 }, total: 1250,
    });

    const r = await ledgerIntegrity.computeLoanSubledgerDrift(BIZ);

    expect(r.reconciled).toBe(true);
    expect(r.accounts.find((a) => a.code === '1145').drift).toBe(0);
  });

  it('flags a break when a loan was repaid in the ledger but not on the item', async () => {
    withBalances([{ code: '1145', derived: 750 }, { code: '1165', derived: 0 }]);
    jest.spyOn(openItemService, 'sumOpenLedger').mockResolvedValue({
      byAccount: { 1145: 1250 }, total: 1250,
    });

    const r = await ledgerIntegrity.computeLoanSubledgerDrift(BIZ);

    expect(r.reconciled).toBe(false);
    expect(r.accounts.find((a) => a.code === '1145').drift).toBe(-500);
  });

  it('reconciles a business with no loans at all', async () => {
    withBalances([{ code: '1145', derived: 0 }, { code: '1165', derived: 0 }]);
    jest.spyOn(openItemService, 'sumOpenLedger').mockResolvedValue({ byAccount: {}, total: 0 });

    const r = await ledgerIntegrity.computeLoanSubledgerDrift(BIZ);
    expect(r.reconciled).toBe(true);
  });

  it('tolerates sub-cent rounding, same standard as the AR/AP gate', async () => {
    withBalances([{ code: '1145', derived: 1250.004 }, { code: '1165', derived: 0 }]);
    jest.spyOn(openItemService, 'sumOpenLedger').mockResolvedValue({
      byAccount: { 1145: 1250 }, total: 1250,
    });

    const r = await ledgerIntegrity.computeLoanSubledgerDrift(BIZ);
    expect(r.reconciled).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/ledgerIntegrity.loans.test.js 2>&1 | tail -15
```

Expected: FAIL — `computeLoanSubledgerDrift is not a function`.

- [ ] **Step 3: Implement**

Add to `services/ledgerIntegrity.service.js` after `computeArApSubledgerDrift` (line 194):

```js
/**
 * VE-7 — the loans sub-ledger.
 *
 * For each loan control account (1145 Loans & Advances to Others, 1165 Employee
 * Loans & Advances), the sum of open loan items posting to it must equal that
 * account's journal-derived balance.
 *
 * Grouped per account rather than summed together: they are separate control
 * accounts, and a compensating error across the two would otherwise hide.
 */
async function computeLoanSubledgerDrift(businessId) {
  const { LOAN_CONTROL_CODES } = require('../config/constants');
  const openItemService = require('./openItem.service');

  const [{ accounts }, open] = await Promise.all([
    module.exports.computeDrift(businessId),
    openItemService.sumOpenLedger(businessId, 'loan'),
  ]);

  const codes = [LOAN_CONTROL_CODES.DEFAULT, LOAN_CONTROL_CODES.EMPLOYEE];
  const rows = codes.map((code) => {
    const controlDerived = r2(accounts.find((a) => a.code === code)?.derived || 0);
    const openItems = r2(open.byAccount?.[code] || 0);
    const drift = r2(controlDerived - openItems);
    return { code, controlDerived, openItems, drift, reconciled: Math.abs(drift) < 0.01 };
  });

  return { accounts: rows, reconciled: rows.every((r) => r.reconciled) };
}
```

Update the exports at line 196:

```js
module.exports = { computeDrift, accountDerivedBalance, recomputeBusinessBalances, computeArApSubledgerDrift, computeLoanSubledgerDrift };
```

> The test spies on `ledgerIntegrity.computeDrift`, so the internal call must go through `module.exports.computeDrift`, not the bare local function — that is why it is written that way above.

Wire it into `services/booksAssurance.service.js` as a sixth check, following the shape of the existing checks in that file (read the file first; each check is an object with a `key`, a `title`, a `passed` boolean and a plain-language `detail`). Use plain copy:

```js
    {
      key: 'loan_subledger',
      title: 'Money you lent adds up',
      passed: loanDrift.reconciled,
      detail: loanDrift.reconciled
        ? 'Every loan you have given out matches your books.'
        : 'Some loans do not match your books. Open Loans & advances to see which.',
    },
```

- [ ] **Step 4: Run the tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/ledgerIntegrity 2>&1 | tail -12
```

Expected: PASS — new file green, existing ledgerIntegrity tests green.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add services/ledgerIntegrity.service.js services/booksAssurance.service.js tests/unit/services/ledgerIntegrity.loans.test.js && git commit -m "feat(loans): VE-7 loan sub-ledger invariant + books-assurance check"
```

## Task 3.5: Full backend suite and a real drift check

- [ ] **Step 1: Run the entire backend suite**

```bash
cd vousfin-backend-main && npm test 2>&1 | tail -25
```

Expected: zero failures, suite count ≥ 301 (baseline) plus the new files.

- [ ] **Step 2: Run the drift script**

```bash
cd vousfin-backend-main && node scripts/ledgerDrift.js 2>&1 | tail -20
```

Expected: drift 0 for every business. **A non-zero reading here blocks the phase** — do not proceed; find and fix the cause.

- [ ] **Step 3: Commit if anything needed fixing, then report**

## Task 3.6: Loans on the Receivables page

**Files:**
- Modify: `vousfin-frontend-main/src/hooks/useParties.js:242-252` (allow `loan`)
- Create: `vousfin-frontend-main/src/components/parties/LoansSection.jsx`
- Create: `vousfin-frontend-main/src/components/parties/LoansSection.test.jsx`
- Modify: `vousfin-frontend-main/src/pages/parties/ReceivablesPage.jsx:164+` (render the section)

**Interfaces:**
- Consumes: `GET /transactions/outstanding?type=loan` (Task 3.3).
- Produces: `<LoansSection currency={string} />`.

- [ ] **Step 1: Write the failing test**

Create `src/components/parties/LoansSection.test.jsx`:

```jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import LoansSection from './LoansSection'

const rows = [
  { _id: 'l1', description: 'Loan to Ali Raza', remainingBalance: 1250, amount: 1250,
    transactionDate: '2026-07-20', customerId: { fullName: 'Ali Raza' } },
  { _id: 'l2', description: 'Advance to Sara', remainingBalance: 500, amount: 500,
    transactionDate: '2026-07-18', customerId: { fullName: 'Sara' } },
]

vi.mock('@/hooks/useParties', () => ({
  useOutstandingBalances: vi.fn(() => ({ data: rows, isLoading: false })),
}))

describe('LoansSection', () => {
  it('lists each person who owes money', () => {
    render(<LoansSection currency="PKR" />)
    expect(screen.getByText('Ali Raza')).toBeInTheDocument()
    expect(screen.getByText('Sara')).toBeInTheDocument()
  })

  it('shows its own total, separate from customer invoices', () => {
    render(<LoansSection currency="PKR" />)
    expect(screen.getByText(/1,750/)).toBeInTheDocument()
  })

  it('uses plain language, not accounting jargon, for the heading', () => {
    render(<LoansSection currency="PKR" />)
    expect(screen.getByRole('heading', { name: /loans & advances/i })).toBeInTheDocument()
    expect(screen.queryByText(/non-trade receivable/i)).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-frontend-main && npx vitest run src/components/parties/LoansSection.test.jsx --reporter=json --outputFile=/tmp/vitest-loan.json 2>&1 | tail -15
```

Expected: FAIL — cannot resolve the component.

- [ ] **Step 3: Implement**

Widen the hook guard in `src/hooks/useParties.js:249`:

```js
    enabled: type === 'receivable' || type === 'payable' || type === 'loan',
```

Create `src/components/parties/LoansSection.jsx`:

```jsx
import { HandCoins } from 'lucide-react'
import { useOutstandingBalances } from '@/hooks/useParties'
import { formatCurrency } from '@/utils/format'

/**
 * Money the business lent to people — kept visually and numerically separate
 * from customer invoices, because they are different things on the books.
 */
export default function LoansSection({ currency }) {
  const { data, isLoading } = useOutstandingBalances('loan')

  const rows = Array.isArray(data?.rows) ? data.rows : Array.isArray(data) ? data : []
  const total = rows.reduce((sum, r) => sum + Number(r.remainingBalance ?? r.amount ?? 0), 0)

  if (isLoading) return null
  if (rows.length === 0) return null

  return (
    <section className="rounded-xl border border-glass bg-charcoal p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary">
          <HandCoins className="h-4 w-4 text-accent" />
          Loans &amp; advances
        </h2>
        <div className="text-right">
          <div className="text-label uppercase tracking-wider text-text-muted">Still owed to you</div>
          <div className="text-lg font-semibold text-text-primary">{formatCurrency(total, currency)}</div>
        </div>
      </div>

      <p className="mb-3 text-small text-text-muted">
        Money you lent out. Kept separate from what customers owe you on invoices.
      </p>

      <ul className="divide-y divide-glass/50">
        {rows.map((r) => {
          const name = r.customerId?.fullName || r.customerId?.businessName || r.partyName || '—'
          return (
            <li key={r._id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <div className="truncate text-small font-medium text-text-primary">{name}</div>
                <div className="truncate text-label text-text-muted">
                  {r.description || 'Loan'}
                  {r.dueDate ? ` · due ${new Date(r.dueDate).toLocaleDateString()}` : ''}
                </div>
              </div>
              <div className="shrink-0 text-small font-semibold text-text-primary">
                {formatCurrency(Number(r.remainingBalance ?? r.amount ?? 0), currency)}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
```

> Check the real export name in `src/utils/format.js` before using `formatCurrency` — if the project's helper is named differently (e.g. `fmtMoney`), use that name and update the test's expectation accordingly.

Render it in `ReceivablesPage.jsx` — in the desktop return, immediately after the existing outstanding table, and in the mobile branch pass it as a child of `MobileOutstanding` (or render it below, matching how that page composes sections):

```jsx
<LoansSection currency={currency} />
```

Import at the top:

```jsx
import LoansSection from '@/components/parties/LoansSection'
```

- [ ] **Step 4: Run tests + build**

```bash
cd vousfin-frontend-main && npx vitest run --reporter=json --outputFile=/tmp/vitest-all.json 2>&1 | tail -5 && node -e "const r=require('/tmp/vitest-all.json');console.log('failed',r.numFailedTests)" && npm run build 2>&1 | tail -5
```

Expected: `failed 0`, build clean.

- [ ] **Step 5: Commit**

```bash
cd vousfin-frontend-main && git add src/components/parties/ src/hooks/useParties.js src/pages/parties/ReceivablesPage.jsx && git commit -m "feat(loans): Loans & advances section on Receivables"
```

- [ ] **Step 6: Live-verify end to end**

With the dev server running: record a loan of 1250 to "Ali Raza", confirm the person is created, the entry appears under Loans & advances with its own total, the customer-invoices total is unchanged, and `GET /reports/books-assurance` still reports all checks passing. Then record a 500 repayment and confirm the balance drops to 750. Screenshot the section.

---

**Phase 3 checkpoint.** Loans work end to end, drift 0, VE-7 green. Stop and report before Phase 4.

---

# Phase 4 — Erase a transaction, permanently

Highest risk in the plan. Read the spec's "doctrine exception" section before starting. The load-bearing safety property is **Task 4.3 Step 3 item 9**: the erase cannot commit unless drift reads 0 inside the same transaction.

## Task 4.1: The archive model

**Files:**
- Create: `vousfin-backend-main/models/ErasedJournalEntry.model.js`
- Test: `vousfin-backend-main/tests/unit/models/ErasedJournalEntry.model.test.js`

**Interfaces:**
- Produces: the `ErasedJournalEntry` mongoose model with fields `businessId`, `originalEntryId`, `snapshot`, `journalLines`, `balancesBefore`, `balancesAfter`, `erasedBy`, `erasedByName`, `erasedAt`, `reason`, `ipAddress`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/models/ErasedJournalEntry.model.test.js`:

```js
'use strict';
const mongoose = require('mongoose');
const ErasedJournalEntry = require('../../../models/ErasedJournalEntry.model');

const BIZ = new mongoose.Types.ObjectId();
const JE  = new mongoose.Types.ObjectId();
const USR = new mongoose.Types.ObjectId();

const valid = () => new ErasedJournalEntry({
  businessId: BIZ,
  originalEntryId: JE,
  snapshot: { _id: JE, amount: 1250, description: 'Typo entry' },
  journalLines: [{ accountId: new mongoose.Types.ObjectId(), type: 'debit', amount: 1250 }],
  balancesBefore: [{ accountId: new mongoose.Types.ObjectId(), accountCode: '1010', runningBalance: 5000 }],
  balancesAfter:  [{ accountId: new mongoose.Types.ObjectId(), accountCode: '1010', runningBalance: 3750 }],
  erasedBy: USR,
  erasedByName: 'Owner',
  reason: 'Duplicate entry created by mistake',
});

describe('ErasedJournalEntry', () => {
  it('accepts a complete archive record', () => {
    expect(valid().validateSync()).toBeUndefined();
  });

  it('requires the business, the original entry, the snapshot and who did it', () => {
    const doc = new ErasedJournalEntry({});
    const err = doc.validateSync();
    expect(err.errors.businessId).toBeDefined();
    expect(err.errors.originalEntryId).toBeDefined();
    expect(err.errors.snapshot).toBeDefined();
    expect(err.errors.erasedBy).toBeDefined();
  });

  it('requires a reason of at least 10 characters', () => {
    const doc = valid();
    doc.reason = 'oops';
    expect(doc.validateSync().errors.reason).toBeDefined();
  });

  it('stamps erasedAt automatically', () => {
    expect(valid().erasedAt).toBeInstanceOf(Date);
  });

  it('indexes by business and original entry for forensic lookup', () => {
    const idx = ErasedJournalEntry.schema.indexes().map(([f]) => Object.keys(f).join(','));
    expect(idx).toContain('businessId,erasedAt');
    expect(idx).toContain('originalEntryId');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/models/ErasedJournalEntry.model.test.js 2>&1 | tail -15
```

Expected: FAIL — cannot find the module.

- [ ] **Step 3: Implement**

Create `models/ErasedJournalEntry.model.js`:

```js
'use strict';
const mongoose = require('mongoose');

/**
 * ErasedJournalEntry — the forensic record of a permanently erased transaction.
 *
 * CLAUDE.md says financial history is permanent. This model is what keeps that
 * true while still letting an owner remove a mistake from their books: the
 * entry leaves the live ledger, but a complete frozen copy of it — and of the
 * account balances on both sides of the erase — lands here first.
 *
 * APPEND-ONLY. No update or delete path is written for this collection, ever.
 * If you find yourself adding one, you are deleting audit history.
 */
const balanceSnapshotSchema = new mongoose.Schema({
  accountId:      { type: mongoose.Schema.Types.ObjectId, ref: 'ChartOfAccount' },
  accountCode:    { type: String, default: '' },
  accountName:    { type: String, default: '' },
  runningBalance: { type: Number, default: 0 },
}, { _id: false });

const erasedJournalEntrySchema = new mongoose.Schema(
  {
    businessId: {
      type: mongoose.Schema.Types.ObjectId, ref: 'Business', required: true, index: true,
    },
    originalEntryId: {
      type: mongoose.Schema.Types.ObjectId, required: true,
    },
    // The complete JournalEntry document, verbatim. Mixed on purpose: the
    // archive must survive future schema changes without losing fields.
    snapshot: { type: mongoose.Schema.Types.Mixed, required: true },
    // The effective lines that were rolled back, resolved at erase time.
    journalLines: { type: [mongoose.Schema.Types.Mixed], default: [] },
    balancesBefore: { type: [balanceSnapshotSchema], default: [] },
    balancesAfter:  { type: [balanceSnapshotSchema], default: [] },
    erasedBy: {
      type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true,
    },
    erasedByName: { type: String, default: '' },
    erasedAt:     { type: Date, default: Date.now, index: true },
    reason: {
      type: String,
      required: true,
      trim: true,
      minlength: [10, 'Say why this entry is being erased — at least a short sentence.'],
      maxlength: 500,
    },
    ipAddress: { type: String, default: '' },
  },
  {
    timestamps: true,
    toJSON: { transform: (doc, ret) => { delete ret.__v; return ret; } },
  }
);

erasedJournalEntrySchema.index({ businessId: 1, erasedAt: -1 });
erasedJournalEntrySchema.index({ originalEntryId: 1 });

module.exports = mongoose.model('ErasedJournalEntry', erasedJournalEntrySchema);
```

- [ ] **Step 4: Run the test**

```bash
cd vousfin-backend-main && npx jest tests/unit/models/ErasedJournalEntry.model.test.js 2>&1 | tail -12
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add models/ErasedJournalEntry.model.js tests/unit/models/ErasedJournalEntry.model.test.js && git commit -m "feat(erase): append-only ErasedJournalEntry archive"
```

## Task 4.2: The eligibility gate

Written as its own module and its own task because it is the whole safety story, and a reviewer should be able to reject it independently of the erase mechanics.

**Files:**
- Create: `vousfin-backend-main/services/eraseEligibility.service.js`
- Test: `vousfin-backend-main/tests/unit/services/eraseEligibility.service.test.js`

**Interfaces:**
- Consumes: models `JournalEntry`, `AccountingPeriod`, `Invoice`, `Bill`, `Payment`, `GoodsReceipt`, `PurchaseOrder`, `CreditNote`, `VendorCredit`, `PayrollRun`, `InstallmentPlan`, `FixedAsset`, `StockMovement`, `TaxReturn`.
- Produces: `checkErasable(businessId, entry, { session }) → Promise<{ erasable: boolean, blockers: Array<{ code, message }> }>`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/eraseEligibility.service.test.js`:

```js
'use strict';
const mongoose = require('mongoose');
const { JOURNAL_STATUS, TRANSACTION_SOURCES } = require('../../../config/constants');

jest.mock('../../../models/AccountingPeriod.model', () => ({
  findCoveringPeriod: jest.fn(async () => ({ name: 'Jul 2026', status: 'open' })),
}));

const AccountingPeriod = require('../../../models/AccountingPeriod.model');
const { checkErasable } = require('../../../services/eraseEligibility.service');
const JournalEntry = require('../../../models/JournalEntry.model');

const BIZ = new mongoose.Types.ObjectId().toString();

const clean = () => ({
  _id: new mongoose.Types.ObjectId(),
  businessId: BIZ,
  transactionDate: new Date('2026-07-20'),
  status: JOURNAL_STATUS.POSTED,
  partiallyPaidAmount: 0,
  settlements: [],
  isProjection: false,
  projectionOf: null,
  reversalOf: null,
  transactionSource: 'manual',
  inventoryItemId: null,
  invoiceNumber: null,
  installmentPlanId: null,
});

// Every "is anything pointing at this entry" lookup resolves to nothing by
// default; individual tests turn one of them on.
const noReferences = () => {
  jest.spyOn(JournalEntry, 'countDocuments').mockResolvedValue(0);
  for (const name of ['Invoice', 'Bill', 'Payment', 'GoodsReceipt', 'PurchaseOrder',
                      'CreditNote', 'VendorCredit', 'PayrollRun', 'InstallmentPlan',
                      'FixedAsset', 'StockMovement', 'TaxReturn']) {
    const Model = require(`../../../models/${name}.model`);
    jest.spyOn(Model, 'countDocuments').mockResolvedValue(0);
  }
};

beforeEach(() => {
  jest.restoreAllMocks();
  AccountingPeriod.findCoveringPeriod.mockResolvedValue({ name: 'Jul 2026', status: 'open' });
  noReferences();
});

describe('checkErasable()', () => {
  it('allows a clean, unsettled, unreferenced entry in an open period', async () => {
    const r = await checkErasable(BIZ, clean(), {});
    expect(r.erasable).toBe(true);
    expect(r.blockers).toHaveLength(0);
  });

  it('blocks a closed period', async () => {
    AccountingPeriod.findCoveringPeriod.mockResolvedValue({ name: 'Jun 2026', status: 'closed' });
    const r = await checkErasable(BIZ, clean(), {});
    expect(r.erasable).toBe(false);
    expect(r.blockers.map((b) => b.code)).toContain('period_closed');
  });

  it('blocks a locked period', async () => {
    AccountingPeriod.findCoveringPeriod.mockResolvedValue({ name: 'Jun 2026', status: 'locked' });
    const r = await checkErasable(BIZ, clean(), {});
    expect(r.blockers.map((b) => b.code)).toContain('period_closed');
  });

  it('blocks when a payment has been applied', async () => {
    const r = await checkErasable(BIZ, { ...clean(), partiallyPaidAmount: 500 }, {});
    expect(r.blockers.map((b) => b.code)).toContain('payment_applied');
  });

  it('blocks when settlements exist even at zero paid', async () => {
    const r = await checkErasable(BIZ, { ...clean(), settlements: [{ amount: 0 }] }, {});
    expect(r.blockers.map((b) => b.code)).toContain('payment_applied');
  });

  it('blocks an already-reversed entry', async () => {
    const r = await checkErasable(BIZ, { ...clean(), status: JOURNAL_STATUS.REVERSED }, {});
    expect(r.blockers.map((b) => b.code)).toContain('already_reversed');
  });

  it('blocks an entry that is itself a reversal', async () => {
    const r = await checkErasable(BIZ, { ...clean(), reversalOf: new mongoose.Types.ObjectId() }, {});
    expect(r.blockers.map((b) => b.code)).toContain('is_a_reversal');
  });

  it('blocks a document projection', async () => {
    const r = await checkErasable(BIZ, { ...clean(), isProjection: true }, {});
    expect(r.blockers.map((b) => b.code)).toContain('document_projection');
  });

  it('blocks a system-generated entry', async () => {
    const r = await checkErasable(BIZ, { ...clean(), transactionSource: 'system_generated' }, {});
    expect(r.blockers.map((b) => b.code)).toContain('system_generated');
  });

  it('blocks when another entry points at it', async () => {
    jest.spyOn(JournalEntry, 'countDocuments').mockResolvedValue(1);
    const r = await checkErasable(BIZ, clean(), {});
    expect(r.blockers.map((b) => b.code)).toContain('referenced_by_entry');
  });

  it('blocks when a payment document points at it', async () => {
    const Payment = require('../../../models/Payment.model');
    jest.spyOn(Payment, 'countDocuments').mockResolvedValue(1);
    const r = await checkErasable(BIZ, clean(), {});
    expect(r.blockers.map((b) => b.code)).toContain('referenced_by_document');
  });

  it('blocks an entry that moved stock', async () => {
    const r = await checkErasable(BIZ, { ...clean(), inventoryItemId: new mongoose.Types.ObjectId() }, {});
    expect(r.blockers.map((b) => b.code)).toContain('inventory_effect');
  });

  it('blocks when a filed tax return covers the date', async () => {
    const TaxReturn = require('../../../models/TaxReturn.model');
    jest.spyOn(TaxReturn, 'countDocuments').mockResolvedValue(1);
    const r = await checkErasable(BIZ, clean(), {});
    expect(r.blockers.map((b) => b.code)).toContain('tax_return_filed');
  });

  it('reports EVERY blocker, not just the first', async () => {
    AccountingPeriod.findCoveringPeriod.mockResolvedValue({ name: 'Jun 2026', status: 'closed' });
    const r = await checkErasable(BIZ, {
      ...clean(), partiallyPaidAmount: 100, status: JOURNAL_STATUS.REVERSED,
    }, {});
    expect(r.blockers.length).toBeGreaterThanOrEqual(3);
  });

  it('writes blockers in plain language, with no jargon', async () => {
    const r = await checkErasable(BIZ, { ...clean(), partiallyPaidAmount: 500 }, {});
    const msg = r.blockers[0].message;
    expect(msg).toMatch(/payment/i);
    expect(msg).not.toMatch(/journal entry|sub-ledger|GAAP/i);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/eraseEligibility.service.test.js 2>&1 | tail -15
```

Expected: FAIL — cannot find `eraseEligibility.service`.

- [ ] **Step 3: Implement**

Create `services/eraseEligibility.service.js`:

```js
'use strict';
/**
 * eraseEligibility — may this entry be erased from the books entirely?
 *
 * Erase is a bounded exception to "financial history is permanent" (spec
 * 2026-07-25). The boundary is this file. An entry may only be erased when it
 * has no accounting consequences yet: nothing settled it, nothing references
 * it, no period closed over it, no tax return reported it. In that state,
 * erasing and reversing leave the ledger identical — erase simply also removes
 * the two confusing rows.
 *
 * Anything with consequences must be REVERSED. This returns every blocker, not
 * the first, so the user does not fix one and immediately hit the next.
 *
 * FAILS CLOSED: an unknown state is a blocker, never a pass.
 */
const { JOURNAL_STATUS } = require('../config/constants');

const REFERENCING_DOCUMENTS = [
  { model: 'Invoice',         fields: ['arJournalId', 'linkedJournalEntryId'], label: 'an invoice' },
  { model: 'Bill',            fields: ['apLiabilityJournalId', 'linkedJournalEntryId'], label: 'a bill' },
  { model: 'Payment',         fields: ['journalEntryId', 'unappliedJournalEntryId'], label: 'a payment' },
  { model: 'GoodsReceipt',    fields: ['journalEntryId'], label: 'a goods receipt' },
  { model: 'PurchaseOrder',   fields: ['journalEntryId'], label: 'a purchase order' },
  { model: 'CreditNote',      fields: ['journalEntryId'], label: 'a credit note' },
  { model: 'VendorCredit',    fields: ['journalEntryId'], label: 'a vendor credit' },
  { model: 'PayrollRun',      fields: ['journalEntryId'], label: 'a payroll run' },
  { model: 'InstallmentPlan', fields: ['parentTransactionId'], label: 'an instalment plan' },
  { model: 'FixedAsset',      fields: ['journalEntryId'], label: 'a fixed asset' },
  { model: 'StockMovement',   fields: ['journalEntryId'], label: 'a stock movement' },
];

/**
 * @returns {Promise<{ erasable: boolean, blockers: Array<{code: string, message: string}> }>}
 */
async function checkErasable(businessId, entry, { session = null } = {}) {
  const blockers = [];
  const add = (code, message) => blockers.push({ code, message });

  if (!entry) {
    add('not_found', 'That entry no longer exists.');
    return { erasable: false, blockers };
  }

  // ── Period ────────────────────────────────────────────────────────────────
  // No admin override here. Unlike posting, there is no escape hatch: erasing
  // out of a closed period would silently change a period someone has signed off.
  const AccountingPeriod = require('../models/AccountingPeriod.model');
  const period = await AccountingPeriod.findCoveringPeriod(businessId, entry.transactionDate);
  if (period && (period.status === 'closed' || period.status === 'locked')) {
    add('period_closed',
      `${period.name} is already closed, so entries in it can't be removed. Reverse it instead.`);
  }

  // ── Settlement ────────────────────────────────────────────────────────────
  if (Number(entry.partiallyPaidAmount) > 0 || (entry.settlements || []).length > 0) {
    add('payment_applied',
      'A payment has already been matched to this. Undo the payment first, or reverse this entry.');
  }

  // ── Reversal state ────────────────────────────────────────────────────────
  if (entry.status === JOURNAL_STATUS.REVERSED) {
    add('already_reversed', 'This one is already reversed, so there is nothing left to remove.');
  }
  if (entry.reversalOf) {
    add('is_a_reversal',
      'This is the correction of another entry. Removing it would bring back the mistake it fixed.');
  }

  // ── Document ownership ────────────────────────────────────────────────────
  if (entry.isProjection === true || entry.projectionOf?.documentId) {
    add('document_projection',
      'This came from an invoice or bill. Delete or void that document instead.');
  }

  // ── System-generated ──────────────────────────────────────────────────────
  if (entry.transactionSource === 'system_generated') {
    add('system_generated',
      'VousFin created this automatically. Fix the thing that caused it, and this will follow.');
  }

  // ── Inventory ─────────────────────────────────────────────────────────────
  if (entry.inventoryItemId) {
    add('inventory_effect',
      'This moved stock. Removing it would leave your stock counts wrong — reverse it instead.');
  }

  const entryId = entry._id;

  // ── Other entries pointing here ───────────────────────────────────────────
  const JournalEntry = require('../models/JournalEntry.model');
  const linkedEntries = await JournalEntry.countDocuments({
    businessId,
    _id: { $ne: entryId },
    $or: [
      { parentTransactionId: entryId },
      { reversalOf: entryId },
      { 'relatedTransactions.transactionId': entryId },
    ],
  }).session(session || null);
  if (linkedEntries > 0) {
    add('referenced_by_entry',
      'Another entry is built on this one. Removing it would leave that entry dangling.');
  }

  // ── Documents pointing here ───────────────────────────────────────────────
  const docHits = await Promise.all(REFERENCING_DOCUMENTS.map(async ({ model, fields, label }) => {
    let Model;
    try { Model = require(`../models/${model}.model`); } catch { return null; }
    const count = await Model.countDocuments({
      businessId,
      $or: fields.map((f) => ({ [f]: entryId })),
    }).session(session || null);
    return count > 0 ? label : null;
  }));
  const hitLabels = docHits.filter(Boolean);
  if (hitLabels.length > 0) {
    add('referenced_by_document',
      `This is linked to ${hitLabels.join(', ')}. Remove that link first, or reverse this entry.`);
  }

  // ── Filed tax return covering the date ────────────────────────────────────
  try {
    const TaxReturn = require('../models/TaxReturn.model');
    const filed = await TaxReturn.countDocuments({
      businessId,
      status: 'filed',
      periodStart: { $lte: entry.transactionDate },
      periodEnd:   { $gte: entry.transactionDate },
    }).session(session || null);
    if (filed > 0) {
      add('tax_return_filed',
        'You have already filed a tax return covering this date. Reverse it instead, so the correction is on the record.');
    }
  } catch {
    // Model absent in a trimmed install — treat as no filings rather than crash.
  }

  return { erasable: blockers.length === 0, blockers };
}

module.exports = { checkErasable, REFERENCING_DOCUMENTS };
```

> Verify the linking field names in each referencing model before finalising — e.g. confirm `Payment` really uses `journalEntryId`. Where a model uses a different name, correct the `fields` array. A wrong field name here means the gate silently passes something it should block, which is the worst possible failure for this feature.

- [ ] **Step 4: Run the test**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/eraseEligibility.service.test.js 2>&1 | tail -15
```

Expected: PASS, 15 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add services/eraseEligibility.service.js tests/unit/services/eraseEligibility.service.test.js && git commit -m "feat(erase): eligibility gate — fails closed, reports every blocker"
```

## Task 4.3: The erase itself

**Files:**
- Modify: `vousfin-backend-main/services/transaction.service.js` (add `eraseTransaction`, `listErasedEntries`)
- Test: `vousfin-backend-main/tests/unit/services/transaction.erase.test.js`

**Interfaces:**
- Consumes: `checkErasable` (Task 4.2); `ErasedJournalEntry` (Task 4.1); `withTransaction`; `accountRepository.updateRunningBalance`; `ledgerIntegrity.computeDrift`; `auditService.log`.
- Produces: `transactionService.eraseTransaction(id, businessId, { reason }, userId, ip) → Promise<{ erasedEntryId, archiveId }>`; `transactionService.listErasedEntries(businessId, { page, limit })`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/transaction.erase.test.js`:

```js
'use strict';
const mongoose = require('mongoose');

jest.mock('../../../services/eraseEligibility.service', () => ({
  checkErasable: jest.fn(async () => ({ erasable: true, blockers: [] })),
}));
jest.mock('../../../services/ledgerIntegrity.service', () => ({
  computeDrift: jest.fn(async () => ({ totalAbsDrift: 0, driftedCount: 0, accounts: [] })),
}));
jest.mock('../../../services/audit.service', () => ({ log: jest.fn(async () => ({})) }));

const eraseEligibility = require('../../../services/eraseEligibility.service');
const ledgerIntegrity = require('../../../services/ledgerIntegrity.service');
const auditService = require('../../../services/audit.service');
const transactionService = require('../../../services/transaction.service');
const JournalEntry = require('../../../models/JournalEntry.model');
const ErasedJournalEntry = require('../../../models/ErasedJournalEntry.model');
const accountRepository = require('../../../repositories/account.repository');

const BIZ = new mongoose.Types.ObjectId().toString();
const DR  = new mongoose.Types.ObjectId();
const CR  = new mongoose.Types.ObjectId();

const entry = () => ({
  _id: new mongoose.Types.ObjectId(),
  businessId: BIZ,
  amount: 1250,
  baseCurrencyAmount: 1250,
  transactionDate: new Date('2026-07-20'),
  description: 'Typo entry',
  debitAccountId: DR,
  creditAccountId: CR,
  journalLines: [
    { accountId: DR, type: 'debit',  amount: 1250 },
    { accountId: CR, type: 'credit', amount: 1250 },
  ],
});

let updateSpy;

beforeEach(() => {
  jest.clearAllMocks();
  jest.restoreAllMocks();
  eraseEligibility.checkErasable.mockResolvedValue({ erasable: true, blockers: [] });
  ledgerIntegrity.computeDrift.mockResolvedValue({ totalAbsDrift: 0, driftedCount: 0, accounts: [] });

  jest.spyOn(accountRepository, 'findById').mockImplementation(async (id) => ({
    _id: id,
    accountCode: String(id) === String(DR) ? '1145' : '1010',
    accountName: 'Acc',
    normalBalance: 'Debit',
    runningBalance: 1000,
  }));
  jest.spyOn(accountRepository, 'findByIdInSession').mockImplementation(async (id) => ({
    _id: id, normalBalance: 'Debit', accountCode: '1010', runningBalance: 1000,
  }));
  updateSpy = jest.spyOn(accountRepository, 'updateRunningBalance').mockResolvedValue({});
  jest.spyOn(ErasedJournalEntry, 'create').mockResolvedValue([{ _id: 'arch1' }]);
  jest.spyOn(JournalEntry, 'deleteOne').mockResolvedValue({ deletedCount: 1 });
});

describe('transactionService.eraseTransaction()', () => {
  it('refuses when the gate says no, and never touches the ledger', async () => {
    const e = entry();
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => e }), lean: async () => e });
    eraseEligibility.checkErasable.mockResolvedValue({
      erasable: false,
      blockers: [{ code: 'payment_applied', message: 'A payment has already been matched to this.' }],
    });

    await expect(transactionService.eraseTransaction(e._id, BIZ, { reason: 'entered twice by mistake' }, 'u1', '1.1.1.1'))
      .rejects.toMatchObject({ statusCode: 409 });

    expect(JournalEntry.deleteOne).not.toHaveBeenCalled();
    expect(updateSpy).not.toHaveBeenCalled();
    expect(ErasedJournalEntry.create).not.toHaveBeenCalled();
  });

  it('archives BEFORE deleting', async () => {
    const e = entry();
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => e }), lean: async () => e });

    const order = [];
    ErasedJournalEntry.create.mockImplementation(async () => { order.push('archive'); return [{ _id: 'arch1' }] });
    JournalEntry.deleteOne.mockImplementation(async () => { order.push('delete'); return { deletedCount: 1 } });

    await transactionService.eraseTransaction(e._id, BIZ, { reason: 'entered twice by mistake' }, 'u1', '1.1.1.1');

    expect(order).toEqual(['archive', 'delete']);
  });

  it('rolls every line back with the exact inverse delta', async () => {
    const e = entry();
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => e }), lean: async () => e });

    await transactionService.eraseTransaction(e._id, BIZ, { reason: 'entered twice by mistake' }, 'u1', '1.1.1.1');

    // Debit-normal account, debit line of 1250 → posting added +1250 → erase subtracts 1250.
    expect(updateSpy).toHaveBeenCalledWith(DR, -1250, expect.anything());
    // Debit-normal account, credit line of 1250 → posting added -1250 → erase adds 1250.
    expect(updateSpy).toHaveBeenCalledWith(CR, 1250, expect.anything());
    expect(updateSpy).toHaveBeenCalledTimes(2);
  });

  it('rolls back and refuses to commit if drift is not zero afterwards', async () => {
    const e = entry();
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => e }), lean: async () => e });
    ledgerIntegrity.computeDrift.mockResolvedValue({ totalAbsDrift: 12.5, driftedCount: 1, accounts: [] });

    await expect(transactionService.eraseTransaction(e._id, BIZ, { reason: 'entered twice by mistake' }, 'u1', '1.1.1.1'))
      .rejects.toThrow(/books/i);
  });

  it('writes an audit log carrying the reason and the full before-state', async () => {
    const e = entry();
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => e }), lean: async () => e });

    await transactionService.eraseTransaction(e._id, BIZ, { reason: 'duplicate of the cash entry' }, 'u1', '1.1.1.1');

    expect(auditService.log).toHaveBeenCalledWith(expect.objectContaining({
      businessId: BIZ,
      action: 'erased',
      performedBy: 'u1',
      beforeState: expect.objectContaining({ amount: 1250 }),
    }));
  });

  it('404s when the entry does not exist', async () => {
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => null }), lean: async () => null });

    await expect(transactionService.eraseTransaction(new mongoose.Types.ObjectId(), BIZ, { reason: 'entered twice by mistake' }, 'u1', '1.1.1.1'))
      .rejects.toMatchObject({ statusCode: 404 });
  });

  it('requires a real reason', async () => {
    const e = entry();
    jest.spyOn(JournalEntry, 'findOne').mockReturnValue({ session: () => ({ lean: async () => e }), lean: async () => e });

    await expect(transactionService.eraseTransaction(e._id, BIZ, { reason: 'x' }, 'u1', '1.1.1.1'))
      .rejects.toMatchObject({ statusCode: 400 });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/transaction.erase.test.js 2>&1 | tail -15
```

Expected: FAIL — `eraseTransaction is not a function`.

- [ ] **Step 3: Implement**

Add to `services/transaction.service.js`, next to `reverseTransaction`:

```js
  /**
   * Erase a transaction from the books, permanently.
   *
   * This is the bounded exception to "financial history is permanent"
   * (spec 2026-07-25). The entry leaves the live ledger; a complete frozen copy
   * goes to the ErasedJournalEntry archive first. The eligibility gate refuses
   * anything with accounting consequences — those must be reversed.
   *
   * SAFETY: the whole thing runs in one transaction and re-verifies ledger drift
   * BEFORE committing. If the books are not provably still square, everything
   * rolls back and the entry is untouched.
   */
  async eraseTransaction(transactionId, businessId, { reason } = {}, userId, ipAddress) {
    const trimmedReason = String(reason || '').trim();
    if (trimmedReason.length < 10) {
      throw new ApiError(400, 'Tell us why you are removing this — a short sentence is enough.');
    }

    const ErasedJournalEntry = require('../models/ErasedJournalEntry.model');
    const { checkErasable } = require('./eraseEligibility.service');
    const ledgerIntegrity = require('./ledgerIntegrity.service');
    const { withTransaction } = require('../utils/withTransaction');

    return withTransaction(async (session) => {
      // Re-read INSIDE the session: a payment could have landed between the
      // user opening the dialog and this running.
      const q = JournalEntry.findOne({ _id: transactionId, businessId });
      const entry = await (typeof q.session === 'function' ? q.session(session || null) : q).lean();
      if (!entry) throw new ApiError(404, 'That entry no longer exists.');

      const { erasable, blockers } = await checkErasable(businessId, entry, { session });
      if (!erasable) {
        const err = new ApiError(
          409,
          `This entry can't be removed: ${blockers.map((b) => b.message).join(' ')}`
        );
        err.blockers = blockers;
        throw err;
      }

      // ── Resolve the effective lines (journalLines first, else the pair) ────
      const lines = Array.isArray(entry.journalLines) && entry.journalLines.length > 0
        ? entry.journalLines
        : [
            { accountId: entry.debitAccountId,  type: 'debit',  amount: entry.baseCurrencyAmount ?? entry.amount },
            { accountId: entry.creditAccountId, type: 'credit', amount: entry.baseCurrencyAmount ?? entry.amount },
          ];

      const snapshotBalances = async () => {
        const seen = new Map();
        for (const l of lines) {
          const key = String(l.accountId);
          if (seen.has(key)) continue;
          const acc = await accountRepository.findById(l.accountId);
          seen.set(key, {
            accountId: l.accountId,
            accountCode: acc?.accountCode || '',
            accountName: acc?.accountName || '',
            runningBalance: acc?.runningBalance ?? 0,
          });
        }
        return [...seen.values()];
      };

      const balancesBefore = await snapshotBalances();

      // ── Archive FIRST. If this fails, nothing else has happened. ───────────
      const [archive] = await ErasedJournalEntry.create([{
        businessId,
        originalEntryId: entry._id,
        snapshot: entry,
        journalLines: lines,
        balancesBefore,
        balancesAfter: [],
        erasedBy: userId,
        erasedByName: '',
        reason: trimmedReason,
        ipAddress: ipAddress || '',
      }], { session });

      // ── Invert every running balance ──────────────────────────────────────
      // The exact opposite of ledgerPosting.applyRunningBalance: a debit line
      // added +amount to a debit-normal account, so we subtract it.
      for (const l of lines) {
        const acc = await accountRepository.findByIdInSession(l.accountId, session);
        if (!acc) {
          throw new ApiError(500, 'One of the accounts on this entry is missing, so it cannot be removed safely. Nothing was changed.');
        }
        const amount = Number(l.amount) || 0;
        const posted = l.type === 'debit'
          ? (acc.normalBalance === 'Debit' ? amount : -amount)
          : (acc.normalBalance === 'Credit' ? amount : -amount);
        await accountRepository.updateRunningBalance(l.accountId, -posted, session);
      }

      // ── Roll back cached party balances ───────────────────────────────────
      await this._rollbackPartyBalance(entry, session);

      // ── Remove the entry ──────────────────────────────────────────────────
      await JournalEntry.deleteOne({ _id: entry._id, businessId }, { session });

      // ── Record the balances the erase landed on ───────────────────────────
      const balancesAfter = await snapshotBalances();
      await ErasedJournalEntry.updateOne(
        { _id: archive._id }, { $set: { balancesAfter } }, { session }
      );

      // ── THE SAFETY GATE ───────────────────────────────────────────────────
      // Prove the books are still square before letting this commit. A throw
      // here rolls the whole transaction back — the entry stays exactly as it was.
      const drift = await ledgerIntegrity.computeDrift(businessId);
      if (drift.totalAbsDrift >= 0.01 || drift.driftedCount > 0) {
        throw new ApiError(
          500,
          'Removing this would have left your books out of balance, so nothing was changed. Reverse the entry instead.'
        );
      }

      await auditService.log({
        businessId,
        entityType: ENTITY_TYPES.JOURNAL_ENTRY,
        entityId: String(entry._id),
        action: 'erased',
        performedBy: userId,
        performedByName: 'User',
        beforeState: entry,
        afterState: null,
        ipAddress,
        metadata: { reason: trimmedReason, archiveId: String(archive._id) },
      });

      return { erasedEntryId: String(entry._id), archiveId: String(archive._id) };
    });
  },

  /**
   * Undo the party-balance cache this entry moved. Trade AR/AP and loans are
   * separate fields and must be rolled back separately.
   */
  async _rollbackPartyBalance(entry, session) {
    const amt = Number(entry.baseCurrencyAmount ?? entry.amount) || 0;
    if (!amt) return;

    if (entry.customerId) {
      const Customer = require('../models/Customer.model');
      const field = entry.transactionType === TRANSACTION_TYPES.LOAN_ISSUED
        ? 'currentLoanBalance'
        : entry.transactionType === TRANSACTION_TYPES.CREDIT_SALE
          ? 'currentReceivableBalance'
          : null;
      if (field) {
        await Customer.updateOne(
          { _id: entry.customerId, businessId: entry.businessId },
          { $inc: { [field]: -amt } },
          { session }
        );
      }
    }

    if (entry.vendorId && entry.transactionType === TRANSACTION_TYPES.CREDIT_PURCHASE) {
      const Vendor = require('../models/Vendor.model');
      await Vendor.updateOne(
        { _id: entry.vendorId, businessId: entry.businessId },
        { $inc: { currentPayableBalance: -amt } },
        { session }
      );
    }
  },

  /**
   * The erased-entries archive — forensic read for auditors.
   */
  async listErasedEntries(businessId, { page = 1, limit = 50 } = {}) {
    const ErasedJournalEntry = require('../models/ErasedJournalEntry.model');
    const skip = (page - 1) * limit;
    const [data, total] = await Promise.all([
      ErasedJournalEntry.find({ businessId })
        .populate('erasedBy', 'fullName email')
        .sort({ erasedAt: -1 })
        .skip(skip)
        .limit(Number(limit))
        .lean(),
      ErasedJournalEntry.countDocuments({ businessId }),
    ]);
    return { data, total, page: Number(page), limit: Number(limit) };
  },
```

> Match the surrounding style: if `transaction.service.js` exports a class instance, these become class methods (drop the trailing commas and the `async name(...)` object-literal form as needed). Read the file's existing structure and follow it exactly.

- [ ] **Step 4: Run the tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/services/transaction.erase.test.js 2>&1 | tail -15
```

Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add services/transaction.service.js tests/unit/services/transaction.erase.test.js && git commit -m "feat(erase): eraseTransaction — archive-first, inverse rollback, drift-verified"
```

## Task 4.4: Permission, routes and controller

**Files:**
- Modify: `vousfin-backend-main/config/constants.js:783` (add `TRANSACTION_ERASE`)
- Modify: `vousfin-backend-main/controllers/transaction.controller.js` (add `eraseTransaction`, `getErasedEntries`)
- Modify: `vousfin-backend-main/routes/v1/transaction.routes.js` (two routes)
- Modify: `vousfin-backend-main/validations/transaction.validation.js` (add `eraseTransactionSchema`)
- Test: `vousfin-backend-main/tests/unit/controllers/transaction.erase.controller.test.js`

**Interfaces:**
- Consumes: `transactionService.eraseTransaction`, `transactionService.listErasedEntries` (Task 4.3).
- Produces: `DELETE /api/v1/transactions/:id/erase`; `GET /api/v1/transactions/erased`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/controllers/transaction.erase.controller.test.js`:

```js
'use strict';
jest.mock('../../../services/transaction.service', () => ({
  eraseTransaction: jest.fn(),
  listErasedEntries: jest.fn(),
}));

const transactionService = require('../../../services/transaction.service');
const transactionController = require('../../../controllers/transaction.controller');
const { PERMISSIONS, ROLE_PERMISSIONS } = require('../../../config/constants');

const mockRes = () => {
  const res = {};
  res.status = jest.fn(() => res);
  res.json = jest.fn(() => res);
  return res;
};
const next = jest.fn();

beforeEach(() => jest.clearAllMocks());

describe('erase permission', () => {
  it('exists as its own permission', () => {
    expect(PERMISSIONS.TRANSACTION_ERASE).toBe('transaction:erase');
  });

  it('is owner-only — an accountant cannot erase', () => {
    expect(ROLE_PERMISSIONS.owner).toContain('*');
    expect(ROLE_PERMISSIONS.accountant).not.toContain('transaction:erase');
    expect(ROLE_PERMISSIONS.approver).not.toContain('transaction:erase');
    expect(ROLE_PERMISSIONS.viewer).not.toContain('transaction:erase');
  });
});

describe('transactionController.eraseTransaction()', () => {
  it('passes the reason through and returns the result', async () => {
    transactionService.eraseTransaction.mockResolvedValue({ erasedEntryId: 'je1', archiveId: 'a1' });
    const req = { params: { id: 'je1' }, body: { reason: 'duplicate of the cash entry' },
                  user: { businessId: 'b1', id: 'u1' }, ip: '1.1.1.1' };

    await transactionController.eraseTransaction(req, mockRes(), next);

    expect(transactionService.eraseTransaction).toHaveBeenCalledWith(
      'je1', 'b1', { reason: 'duplicate of the cash entry' }, 'u1', '1.1.1.1'
    );
    expect(next).not.toHaveBeenCalled();
  });

  it('forwards a gate refusal to the error handler untouched', async () => {
    const err = Object.assign(new Error('blocked'), { statusCode: 409 });
    transactionService.eraseTransaction.mockRejectedValue(err);
    const req = { params: { id: 'je1' }, body: { reason: 'duplicate of the cash entry' },
                  user: { businessId: 'b1', id: 'u1' }, ip: '1.1.1.1' };

    await transactionController.eraseTransaction(req, mockRes(), next);

    expect(next).toHaveBeenCalledWith(err);
  });
});

describe('transactionController.getErasedEntries()', () => {
  it('lists the archive for the caller business only', async () => {
    transactionService.listErasedEntries.mockResolvedValue({ data: [], total: 0 });
    const req = { query: { page: '2', limit: '10' }, user: { businessId: 'b1', id: 'u1' } };

    await transactionController.getErasedEntries(req, mockRes(), next);

    expect(transactionService.listErasedEntries).toHaveBeenCalledWith('b1', { page: 2, limit: 10 });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-backend-main && npx jest tests/unit/controllers/transaction.erase.controller.test.js 2>&1 | tail -15
```

Expected: FAIL — `PERMISSIONS.TRANSACTION_ERASE` is undefined.

- [ ] **Step 3: Implement**

In `config/constants.js`, after line 783:

```js
    // Remove an entry from the books entirely (spec 2026-07-25). Strictly more
    // dangerous than a reversal, so it is its own permission. ROLE_PERMISSIONS
    // is deliberately NOT changed: owner has '*', and every other role's list is
    // explicit — so this is owner-only with no extra wiring.
    TRANSACTION_ERASE:   'transaction:erase',
```

Add to `validations/transaction.validation.js`:

```js
const eraseTransactionSchema = Joi.object({
  reason: Joi.string().trim().min(10).max(500).required()
    .messages({ 'string.min': 'Tell us why you are removing this — a short sentence is enough.' }),
});
```

Export it. Add to `controllers/transaction.controller.js`:

```js
/**
 * Erase a transaction from the books, permanently.
 * DELETE /api/v1/transactions/:id/erase
 */
const eraseTransaction = async (req, res, next) => {
  try {
    const result = await transactionService.eraseTransaction(
      req.params.id, req.user.businessId, { reason: req.body.reason }, req.user.id, req.ip
    );
    ApiResponse.success(res, result, 'Entry removed from your books');
  } catch (error) {
    next(error);
  }
};

/**
 * The erased-entries archive (forensic read).
 * GET /api/v1/transactions/erased
 */
const getErasedEntries = async (req, res, next) => {
  try {
    const result = await transactionService.listErasedEntries(req.user.businessId, {
      page: parseInt(req.query.page, 10) || 1,
      limit: parseInt(req.query.limit, 10) || 50,
    });
    ApiResponse.success(res, result, 'Erased entries retrieved');
  } catch (error) {
    next(error);
  }
};
```

Export both. Add the routes in `routes/v1/transaction.routes.js` — `/erased` must sit with the other literal paths **before** `/:id` (line 77):

```js
// ── Erased-entry archive (forensic) ───────────────────────────────────────────
router.get('/erased', requirePermission(PERMISSIONS.AUDIT_MANAGE), transactionController.getErasedEntries);
```

And after the reverse route (line 83):

```js
// ── Permanent erase — spec 2026-07-25. Strictly more dangerous than reverse. ──
router.delete('/:id/erase',
  validate(transactionIdParamSchema, 'params'),
  validate(eraseTransactionSchema),
  requirePermission(PERMISSIONS.TRANSACTION_ERASE),
  transactionController.eraseTransaction);
```

Leave the legacy `router.delete('/:id', …)` at line 80 exactly as it is.

- [ ] **Step 4: Run the tests**

```bash
cd vousfin-backend-main && npx jest tests/unit/controllers/transaction.erase.controller.test.js 2>&1 | tail -12
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
cd vousfin-backend-main && git add config/constants.js controllers/transaction.controller.js routes/v1/transaction.routes.js validations/transaction.validation.js tests/unit/controllers/transaction.erase.controller.test.js && git commit -m "feat(erase): owner-only erase route + erased-entries archive read"
```

## Task 4.5: Full suite and drift

- [ ] **Step 1: Run the whole backend suite**

```bash
cd vousfin-backend-main && npm test 2>&1 | tail -25
```

Expected: zero failures.

- [ ] **Step 2: Drift must read 0**

```bash
cd vousfin-backend-main && node scripts/ledgerDrift.js 2>&1 | tail -20
```

Expected: 0 for every business. Non-zero blocks the phase.

## Task 4.6: The erase action in the UI

**Files:**
- Create: `vousfin-frontend-main/src/components/modals/EraseTransactionDialog.jsx`
- Create: `vousfin-frontend-main/src/components/modals/EraseTransactionDialog.test.jsx`
- Modify: `vousfin-frontend-main/src/services/transaction.service.js` (add `eraseTransaction`)
- Modify: `vousfin-frontend-main/src/components/modals/TransactionDetailModal.jsx` (add the danger action)

**Interfaces:**
- Consumes: `DELETE /transactions/:id/erase` (Task 4.4); `Can` from `@/components/Can`.
- Produces: `<EraseTransactionDialog transaction={obj} isOpen onClose onErased />`.

- [ ] **Step 1: Write the failing test**

Create `src/components/modals/EraseTransactionDialog.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import EraseTransactionDialog from './EraseTransactionDialog'
import transactionService from '@/services/transaction.service'

vi.mock('@/services/transaction.service', () => ({
  default: { eraseTransaction: vi.fn(async () => ({ data: { data: {} } })) },
}))

const txn = { _id: 'je1', description: 'Duplicate payment', amount: 1250 }

beforeEach(() => vi.clearAllMocks())

describe('EraseTransactionDialog', () => {
  it('keeps the erase button disabled until a real reason is typed', () => {
    render(<EraseTransactionDialog transaction={txn} isOpen onClose={() => {}} />)
    const btn = screen.getByRole('button', { name: /remove it/i })
    expect(btn).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/why/i), { target: { value: 'oops' } })
    expect(btn).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/why/i), { target: { value: 'entered this twice by mistake' } })
    expect(btn).toBeEnabled()
  })

  it('sends the reason to the server', async () => {
    render(<EraseTransactionDialog transaction={txn} isOpen onClose={() => {}} onErased={() => {}} />)
    fireEvent.change(screen.getByLabelText(/why/i), { target: { value: 'entered this twice by mistake' } })
    fireEvent.click(screen.getByRole('button', { name: /remove it/i }))

    await waitFor(() => expect(transactionService.eraseTransaction)
      .toHaveBeenCalledWith('je1', 'entered this twice by mistake'))
  })

  it('warns that this cannot be undone', () => {
    render(<EraseTransactionDialog transaction={txn} isOpen onClose={() => {}} />)
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument()
  })

  it('shows the server blockers and offers reversal when the erase is refused', async () => {
    transactionService.eraseTransaction.mockRejectedValue({
      response: { data: { message: 'A payment has already been matched to this.' } },
    })
    render(<EraseTransactionDialog transaction={txn} isOpen onClose={() => {}} />)
    fireEvent.change(screen.getByLabelText(/why/i), { target: { value: 'entered this twice by mistake' } })
    fireEvent.click(screen.getByRole('button', { name: /remove it/i }))

    await waitFor(() => expect(screen.getByText(/payment has already been matched/i)).toBeInTheDocument())
    expect(screen.getByText(/reverse it instead/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd vousfin-frontend-main && npx vitest run src/components/modals/EraseTransactionDialog.test.jsx --reporter=json --outputFile=/tmp/vitest-erase.json 2>&1 | tail -15
```

Expected: FAIL — cannot resolve the component.

- [ ] **Step 3: Implement**

Add to `src/services/transaction.service.js`:

```js
  eraseTransaction: (id, reason) =>
    api.delete(`/transactions/${id}/erase`, { data: { reason } }),
```

Create `src/components/modals/EraseTransactionDialog.jsx`:

```jsx
import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'
import Modal from './Modal'
import transactionService from '@/services/transaction.service'
import { getErrorMessage } from '@/utils/errorHandler'

/**
 * Permanent removal. Deliberately higher friction than reversing: a typed
 * reason, an explicit warning, and the server's refusal shown in full when the
 * entry is not eligible.
 */
export default function EraseTransactionDialog({ transaction, isOpen, onClose, onErased }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [refusal, setRefusal] = useState(null)

  if (!transaction) return null

  const ready = reason.trim().length >= 10

  const submit = async () => {
    setBusy(true)
    setRefusal(null)
    try {
      await transactionService.eraseTransaction(transaction._id, reason.trim())
      toast.success('Entry removed from your books')
      setReason('')
      onErased?.()
      onClose?.()
    } catch (err) {
      setRefusal(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Remove this entry?">
      <div className="space-y-4">
        <div className="flex gap-3 rounded-lg border border-negative/30 bg-negative/10 p-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-negative" />
          <div className="text-small text-text-primary">
            <p className="font-medium">This cannot be undone.</p>
            <p className="mt-1 text-text-secondary">
              The entry is removed from your books completely. A copy is kept privately for your records.
              If you only want to correct a mistake, reversing is usually the better choice.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-glass bg-glass-panel/40 p-3 text-small">
          <div className="font-medium text-text-primary">{transaction.description}</div>
          <div className="text-text-muted">{transaction.transactionType} · {transaction.amount}</div>
        </div>

        <div>
          <label htmlFor="erase-reason" className="text-label uppercase tracking-wider text-text-muted">
            Why are you removing it?
          </label>
          <textarea
            id="erase-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="For example: I entered this twice by mistake"
            className="mt-1 w-full resize-none rounded-lg border border-glass bg-glass-panel/40 px-3 py-2 text-small focus:border-accent/40 focus:outline-none"
          />
        </div>

        {refusal && (
          <div role="alert" className="rounded-lg border border-highlight/30 bg-highlight/10 p-3 text-small">
            <p className="text-text-primary">{refusal}</p>
            <p className="mt-1 text-text-secondary">Reverse it instead — that keeps the correction on the record.</p>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-glass px-4 py-2 text-small text-text-primary hover:bg-glass-hover"
          >
            Keep it
          </button>
          <button
            onClick={submit}
            disabled={!ready || busy}
            className="rounded-lg bg-negative px-4 py-2 text-small font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? 'Removing…' : 'Yes, remove it'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
```

In `TransactionDetailModal.jsx`, add the trigger wrapped in the permission gate (follow the file's existing `Can` usage; read it first):

```jsx
<Can permission="transaction:erase">
  <button
    onClick={() => setErasing(true)}
    className="text-small text-negative hover:underline"
  >
    Remove permanently
  </button>
</Can>

<EraseTransactionDialog
  transaction={transaction}
  isOpen={erasing}
  onClose={() => setErasing(false)}
  onErased={onRefresh}
/>
```

- [ ] **Step 4: Run tests + build**

```bash
cd vousfin-frontend-main && npx vitest run --reporter=json --outputFile=/tmp/vitest-all.json 2>&1 | tail -5 && node -e "const r=require('/tmp/vitest-all.json');console.log('failed',r.numFailedTests)" && npm run build 2>&1 | tail -5
```

Expected: `failed 0`, build clean.

- [ ] **Step 5: Commit**

```bash
cd vousfin-frontend-main && git add src/components/modals/ src/services/transaction.service.js && git commit -m "feat(erase): permanent-removal dialog with typed reason and blocker feedback"
```

- [ ] **Step 6: Live-verify**

With the dev server running:
1. Post a throwaway entry, erase it, confirm it disappears from the list entirely (no reversal row) and that `GET /reports/books-assurance` still passes.
2. Post an entry, apply a payment to it, then try to erase — confirm the refusal names the payment and offers reversal.
3. Run `node scripts/ledgerDrift.js` — must read 0.
4. Erase the original mis-recorded 1250 loan entry and re-record it through the new loan flow.

---

**Phase 4 checkpoint.** All four features shipped. Report the final state: backend suite count, frontend suite count, drift reading, and what remains unpushed.

---

# Self-review notes

- **Spec coverage.** Feature 1 → Tasks 3.1–3.6. Feature 2 → Tasks 4.1–4.6. Feature 3 → Tasks 2.1–2.4. Feature 4 → Tasks 1.1–1.3. Two spec items are deliberately deferred and are **not** in this plan: the NL `loan_issued` intent and the Excel-import keyword rules (spec Feature 1, "Frontend" bullets 3–4). They are additive polish on top of a working loan flow; add them as a follow-up once Phase 3 is verified live.
- **Naming consistency.** `LOAN_CONTROL_CODES` (3.1) → used in 3.3 and 3.4. `getOutstandingLoans` (3.2) → used in 3.2's `openItems`. `buildFilterQuery` (2.1) → used in 2.2. `checkErasable` (4.2) → used in 4.3. `EXPORT_ROW_CAP` (2.2) → used in 2.3.
- **Known verification points flagged inline** rather than assumed: the `formatCurrency` export name (3.6), the referencing-model field names (4.2), whether `transaction.service.js` is a class or an object literal (4.3), and whether `EFFECTIVE_LINES_STAGE` is already in the repository's `module.exports` (2.2). Each is called out at its step.
