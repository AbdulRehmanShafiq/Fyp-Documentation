# VousFin Command Bar — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an accessible, instant, keyboard-first command bar (`⌘/Ctrl+K` or `/`) that finds and jumps to any VousFin module, page, or quick action — built entirely from the existing `nav.config.js` catalog with zero new backend infra.

**Architecture:** A pure derivation flattens `MODULES` into searchable entries. A hand-rolled, zero-dependency matcher ranks them. An accessible WAI-ARIA combobox renders grouped results and deep-links on Enter. All client-side and offline (Tier 1 of the three-tier design); Tiers 2–3 (semantic + how-to) are later phases.

**Tech Stack:** React 19, Vite, Zustand, react-router-dom v6, lucide-react, Tailwind. New dev dependency: Vitest + @testing-library/react (the frontend currently has no test runner).

**Spec:** `docs/superpowers/specs/2026-06-30-vousfin-command-bar-intelligent-search-design.md`

## Global Constraints

- **Card-free:** no paid services, no new runtime infra. Phase 1 is 100% client-side.
- **Zero new runtime deps:** the matcher is hand-rolled (no Fuse.js). New deps are **dev-only** (test runner).
- **Single source of truth:** the catalog derives from `src/components/layout/nav.config.js` `MODULES` — never a second hand-maintained list.
- **Accessibility is in-scope from day one:** WAI-ARIA combobox/listbox, full keyboard, `aria-live` result counts, focus trap + restore, `prefers-reduced-motion`, RTL-safe. WCAG 2.1 AA.
- **Plain language:** user-facing copy is plain (non-accountant owner), per platform rule. Accounting terms live in `synonyms`, not primary labels.
- **Frontend `@/` alias maps to `src/`** (configured in `vite.config.js`).
- **All new code under** `vousfin-frontend-main/src/features/command-bar/`.

---

### Task 1: Add a frontend test runner (Vitest)

**Files:**
- Modify: `vousfin-frontend-main/package.json` (add devDeps + `test` script)
- Create: `vousfin-frontend-main/vitest.config.js`
- Create: `vousfin-frontend-main/src/test/setup.js`
- Test: `vousfin-frontend-main/src/test/smoke.test.js`

**Interfaces:**
- Produces: a working `npm test` (Vitest, jsdom env, `@testing-library/jest-dom` matchers, `@/` alias) that all later tasks rely on.

- [ ] **Step 1: Install dev dependencies**

Run (from `vousfin-frontend-main/`):
```bash
npm i -D vitest@^2 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 2: Add the test script to package.json**

In `vousfin-frontend-main/package.json`, add to `"scripts"`:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 3: Create the Vitest config**

Create `vousfin-frontend-main/vitest.config.js`:
```js
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
  },
})
```

- [ ] **Step 4: Create the test setup file**

Create `vousfin-frontend-main/src/test/setup.js`:
```js
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 5: Write a smoke test**

Create `vousfin-frontend-main/src/test/smoke.test.js`:
```js
import { describe, it, expect } from 'vitest'

describe('test runner', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2)
  })
})
```

- [ ] **Step 6: Run it and verify it passes**

Run: `npm test`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json vitest.config.js src/test/
git commit -m "test(frontend): add Vitest + Testing Library runner"
```

---

### Task 2: Catalog entry type + derivation from MODULES

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/catalog.js`
- Test: `vousfin-frontend-main/src/features/command-bar/catalog.test.js`

**Interfaces:**
- Consumes: `MODULES` from `@/components/layout/nav.config.js`.
- Produces: `deriveCatalog(modules) -> Entry[]` where
  `Entry = { id:string, type:'module'|'page'|'action', title:string, path:string[], href:string, icon:Component, synonyms:string[], moduleKey:string, enablementKey:string|null }`.
  Also exports `slug(text) -> string`.

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/catalog.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { deriveCatalog, slug } from './catalog'
import { MODULES } from '@/components/layout/nav.config.js'

const catalog = deriveCatalog(MODULES)
const byId = (id) => catalog.find((e) => e.id === id)

describe('deriveCatalog', () => {
  it('emits a module entry for each top-level module', () => {
    const sales = byId('sales')
    expect(sales).toBeTruthy()
    expect(sales.type).toBe('module')
    expect(sales.href).toBe('/sales')
    expect(sales.path).toEqual(['Sales'])
  })

  it('emits a page entry for each sub-item with a breadcrumb path', () => {
    const invoices = byId('sales.invoices')
    expect(invoices.type).toBe('page')
    expect(invoices.title).toBe('Invoices')
    expect(invoices.href).toBe('/sales/invoices')
    expect(invoices.path).toEqual(['Sales', 'Invoices'])
  })

  it('carries the module tag and item desc into synonyms', () => {
    const receivables = byId('sales.receivables')
    // module tag "Accounts Receivable" + desc tokens are searchable synonyms
    expect(receivables.synonyms.join(' ')).toMatch(/receivable/i)
  })

  it('marks enableable (alwaysOn:false) modules with an enablementKey', () => {
    expect(byId('payroll').enablementKey).toBe('payroll')
    expect(byId('sales').enablementKey).toBeNull()
  })

  it('produces globally-unique ids', () => {
    const ids = catalog.map((e) => e.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

describe('slug', () => {
  it('normalizes a label to a stable token', () => {
    expect(slug('New Invoice')).toBe('new-invoice')
    expect(slug('AR Aging')).toBe('ar-aging')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- catalog`
Expected: FAIL — "Failed to resolve import './catalog'".

- [ ] **Step 3: Implement the derivation**

Create `vousfin-frontend-main/src/features/command-bar/catalog.js`:
```js
/**
 * catalog.js — flatten nav.config MODULES into searchable command-bar entries.
 * This is the SINGLE source of truth: never hand-maintain a parallel list.
 */

export function slug(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function tokens(text) {
  return String(text || '')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
}

/**
 * @param {Array} modules  the MODULES array from nav.config.js
 * @returns {Array<Entry>}
 */
export function deriveCatalog(modules) {
  const entries = []
  for (const m of modules) {
    const enablementKey = m.alwaysOn === false ? m.key : null
    // module-level entry
    entries.push({
      id: m.key,
      type: 'module',
      title: m.name,
      path: [m.name],
      href: m.href,
      icon: m.icon,
      synonyms: [...tokens(m.subtitle), ...tokens(m.tag)],
      moduleKey: m.key,
      enablementKey,
    })
    // page-level entries
    for (const item of m.items || []) {
      entries.push({
        id: `${m.key}.${slug(item.name)}`,
        type: item.__action ? 'action' : 'page',
        title: item.name,
        path: [m.name, item.name],
        href: item.href,
        icon: item.icon,
        synonyms: [...tokens(item.desc), ...tokens(m.tag), ...tokens(m.name)],
        moduleKey: m.key,
        enablementKey,
      })
    }
  }
  return entries
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- catalog`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/catalog.js src/features/command-bar/catalog.test.js
git commit -m "feat(command-bar): derive searchable catalog from nav.config MODULES"
```

---

### Task 3: Synonyms map (plain-word ↔ accounting term)

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/synonyms.js`
- Modify: `vousfin-frontend-main/src/features/command-bar/catalog.js` (merge synonyms in)
- Test: `vousfin-frontend-main/src/features/command-bar/synonyms.test.js`

**Interfaces:**
- Produces: `SYNONYMS: Record<entryId, string[]>` and `expandSynonyms(entry) -> string[]`.
- Modifies `deriveCatalog` to append `SYNONYMS[entry.id]` into each entry's `synonyms`.

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/synonyms.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { deriveCatalog } from './catalog'
import { MODULES } from '@/components/layout/nav.config.js'

const byId = (id) => deriveCatalog(MODULES).find((e) => e.id === id)

describe('synonyms', () => {
  it('maps the plain phrase "who owes me" onto Receivables', () => {
    expect(byId('sales.receivables').synonyms).toContain('who owes me')
  })
  it('maps "what i owe" onto Payables', () => {
    expect(byId('purchases.payables').synonyms).toContain('what i owe')
  })
  it('maps "reconcile" onto Bank Reconciliation', () => {
    expect(byId('banking.bank-reconciliation').synonyms).toContain('reconcile')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- synonyms`
Expected: FAIL — "Failed to resolve import './synonyms'".

- [ ] **Step 3: Create the synonyms map**

Create `vousfin-frontend-main/src/features/command-bar/synonyms.js`:
```js
/**
 * synonyms.js — plain-language phrases mapped onto catalog entry ids.
 * The primary relevance-tuning lever. Keys are entry ids from catalog.js.
 * Phrases are stored lowercased; the matcher normalizes queries the same way.
 */
export const SYNONYMS = {
  'sales.receivables':            ['who owes me', 'money owed to me', 'debtors', 'outstanding customers'],
  'sales.ar-aging':               ['overdue customers', 'how late are payments'],
  'purchases.payables':           ['what i owe', 'money i owe', 'creditors', 'unpaid bills'],
  'banking.bank-reconciliation':  ['reconcile', 'match the bank', 'bank matching'],
  'accounting.chart-of-accounts': ['accounts list', 'ledger accounts', 'coa'],
  'reports.financial-statements': ['profit and loss', 'p&l', 'pnl', 'balance sheet', 'cash flow'],
  'accounting.inventory':         ['stock', 'stock on hand'],
}

export function expandSynonyms(entry) {
  return SYNONYMS[entry.id] || []
}
```

- [ ] **Step 4: Merge synonyms into the derivation**

In `vousfin-frontend-main/src/features/command-bar/catalog.js`, add the import at the top:
```js
import { SYNONYMS } from './synonyms'
```
Then, in `deriveCatalog`, change BOTH `synonyms:` assignments to append the curated phrases. For the module entry:
```js
      synonyms: [...tokens(m.subtitle), ...tokens(m.tag), ...(SYNONYMS[m.key] || [])],
```
For the page/action entry (replace its `synonyms:` line):
```js
        synonyms: [
          ...tokens(item.desc), ...tokens(m.tag), ...tokens(m.name),
          ...(SYNONYMS[`${m.key}.${slug(item.name)}`] || []),
        ],
```

- [ ] **Step 5: Run both test files to verify they pass**

Run: `npm test -- synonyms catalog`
Expected: PASS (synonyms 3, catalog 6). The catalog test still passes because synonyms are appended, not replaced.

- [ ] **Step 6: Commit**

```bash
git add src/features/command-bar/synonyms.js src/features/command-bar/synonyms.test.js src/features/command-bar/catalog.js
git commit -m "feat(command-bar): plain-language synonym map for catalog entries"
```

---

### Task 4: Quick-action entries

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/actions.js`
- Test: `vousfin-frontend-main/src/features/command-bar/actions.test.js`

**Interfaces:**
- Produces: `withActions(entries) -> Entry[]` — re-types entries that are create-flows (`type:'action'`) and prepends a verb to the title (e.g. "New Invoice" stays, "Invoices" is untouched). Detection: `href` ends with `/new`, or `title` starts with `New `/`Run `.

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/actions.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { deriveCatalog } from './catalog'
import { withActions } from './actions'
import { MODULES } from '@/components/layout/nav.config.js'

const entries = withActions(deriveCatalog(MODULES))
const byId = (id) => entries.find((e) => e.id === id)

describe('withActions', () => {
  it('types a create-flow page as an action', () => {
    expect(byId('sales.new-invoice').type).toBe('action')
  })
  it('types "Run Payroll" as an action', () => {
    expect(byId('payroll.run-payroll').type).toBe('action')
  })
  it('leaves a normal page as a page', () => {
    expect(byId('sales.invoices').type).toBe('page')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- actions`
Expected: FAIL — "Failed to resolve import './actions'".

- [ ] **Step 3: Implement the action detection**

Create `vousfin-frontend-main/src/features/command-bar/actions.js`:
```js
/**
 * actions.js — re-type create-flow entries as quick actions so the command bar
 * can surface "do" results (New Invoice, Run Payroll) distinctly from "go" pages.
 */
const ACTION_TITLE = /^(new|run|create|add|record)\s/i

export function isAction(entry) {
  return /\/new$/.test(entry.href || '') || ACTION_TITLE.test(entry.title || '')
}

export function withActions(entries) {
  return entries.map((e) =>
    e.type === 'page' && isAction(e) ? { ...e, type: 'action' } : e
  )
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- actions`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/actions.js src/features/command-bar/actions.test.js
git commit -m "feat(command-bar): classify create-flows as quick actions"
```

---

### Task 5: The matcher (ranking)

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/matcher.js`
- Test: `vousfin-frontend-main/src/features/command-bar/matcher.test.js`

**Interfaces:**
- Consumes: `Entry[]` from the catalog tasks.
- Produces: `searchCatalog(entries, query, { limit = 8 }) -> Entry[]` ranked best-first; empty query returns `[]`. Also exports `scoreEntry(entry, normalizedQuery) -> number` (0 = no match).

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/matcher.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { deriveCatalog } from './catalog'
import { withActions } from './actions'
import { searchCatalog } from './matcher'
import { MODULES } from '@/components/layout/nav.config.js'

const entries = withActions(deriveCatalog(MODULES))
const topId = (q) => searchCatalog(entries, q, { limit: 5 })[0]?.id

// Labeled query -> expected top result (per-persona relevance set)
const CASES = [
  ['invoices', 'sales.invoices'],
  ['new invoice', 'sales.new-invoice'],
  ['who owes me', 'sales.receivables'],
  ['what i owe', 'purchases.payables'],
  ['reconcile', 'banking.bank-reconciliation'],
  ['chart of accounts', 'accounting.chart-of-accounts'],
  ['profit and loss', 'reports.financial-statements'],
  ['payslips', 'payroll.payslips'],
]

describe('searchCatalog', () => {
  it.each(CASES)('ranks "%s" -> %s as the top result', (q, expected) => {
    expect(topId(q)).toBe(expected)
  })

  it('returns nothing for an empty query', () => {
    expect(searchCatalog(entries, '   ', {})).toEqual([])
  })

  it('respects the limit', () => {
    expect(searchCatalog(entries, 'a', { limit: 3 }).length).toBeLessThanOrEqual(3)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- matcher`
Expected: FAIL — "Failed to resolve import './matcher'".

- [ ] **Step 3: Implement the matcher**

Create `vousfin-frontend-main/src/features/command-bar/matcher.js`:
```js
/**
 * matcher.js — hand-rolled, dependency-free ranking for the command bar.
 * Scoring tiers (high → low): exact title, title prefix, whole-word token,
 * synonym phrase, then subsequence (fuzzy). Transparent and unit-tested so
 * relevance is tunable without a black-box library.
 */
function normalize(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim()
}

function isSubsequence(needle, haystack) {
  let i = 0
  for (let j = 0; j < haystack.length && i < needle.length; j++) {
    if (needle[i] === haystack[j]) i++
  }
  return i === needle.length
}

export function scoreEntry(entry, q) {
  const title = normalize(entry.title)
  const titleTokens = title.split(' ')
  const synonyms = (entry.synonyms || []).map(normalize)
  const haystack = [title, ...entry.path.map(normalize), ...synonyms].join(' ')

  if (!q) return 0
  if (title === q) return 100
  if (title.startsWith(q)) return 85
  if (titleTokens.some((t) => t.startsWith(q))) return 70
  if (synonyms.some((s) => s === q)) return 65
  if (synonyms.some((s) => s.includes(q))) return 55
  if (haystack.includes(q)) return 45
  // multi-word query: every word must appear somewhere
  const words = q.split(' ').filter(Boolean)
  if (words.length > 1 && words.every((w) => haystack.includes(w))) return 40
  if (isSubsequence(q.replace(/\s/g, ''), title.replace(/\s/g, ''))) return 20
  return 0
}

export function searchCatalog(entries, query, { limit = 8 } = {}) {
  const q = normalize(query)
  if (!q) return []
  return entries
    .map((e) => ({ e, s: scoreEntry(e, q) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s || a.e.title.length - b.e.title.length)
    .slice(0, limit)
    .map((x) => x.e)
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- matcher`
Expected: PASS (all 10). If any labeled case fails, adjust that entry's `synonyms` in `synonyms.js` — NOT the score thresholds — then re-run.

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/matcher.js src/features/command-bar/matcher.test.js
git commit -m "feat(command-bar): hand-rolled ranked matcher with relevance test set"
```

---

### Task 6: Enablement filter

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/filter.js`
- Test: `vousfin-frontend-main/src/features/command-bar/filter.test.js`

**Interfaces:**
- Produces: `filterByEnablement(entries, enabledModuleKeys) -> Entry[]`. An entry is visible if `enablementKey` is null (always-on) OR `enabledModuleKeys` includes it.

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/filter.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { deriveCatalog } from './catalog'
import { filterByEnablement } from './filter'
import { MODULES } from '@/components/layout/nav.config.js'

const entries = deriveCatalog(MODULES)

describe('filterByEnablement', () => {
  it('hides an enableable module that is not enabled', () => {
    const visible = filterByEnablement(entries, []) // nothing extra enabled
    expect(visible.some((e) => e.id === 'payroll')).toBe(false)
  })
  it('shows an enableable module when enabled', () => {
    const visible = filterByEnablement(entries, ['payroll'])
    expect(visible.some((e) => e.id === 'payroll')).toBe(true)
  })
  it('always shows always-on modules', () => {
    const visible = filterByEnablement(entries, [])
    expect(visible.some((e) => e.id === 'sales')).toBe(true)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- filter`
Expected: FAIL — "Failed to resolve import './filter'".

- [ ] **Step 3: Implement the filter**

Create `vousfin-frontend-main/src/features/command-bar/filter.js`:
```js
/**
 * filter.js — hide entries for modules this business hasn't enabled.
 * Always-on modules (enablementKey === null) are always visible.
 */
export function filterByEnablement(entries, enabledModuleKeys = []) {
  const enabled = new Set(enabledModuleKeys)
  return entries.filter((e) => e.enablementKey == null || enabled.has(e.enablementKey))
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- filter`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/filter.js src/features/command-bar/filter.test.js
git commit -m "feat(command-bar): filter catalog by enabled modules"
```

---

### Task 7: Command-bar store + memoized catalog facade

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/useCommandBar.js`
- Test: `vousfin-frontend-main/src/features/command-bar/useCommandBar.test.js`

**Interfaces:**
- Consumes: `deriveCatalog`, `withActions`, `searchCatalog`, `filterByEnablement`.
- Produces: a Zustand store `useCommandBar` with state `{ open, query }` and actions `{ openBar(), closeBar(), setQuery(q) }`; plus a pure selector `getResults(query, enabledModuleKeys, limit) -> Entry[]` exported separately (memoized catalog build).

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/useCommandBar.test.js`:
```js
import { describe, it, expect, beforeEach } from 'vitest'
import { useCommandBar, getResults } from './useCommandBar'

describe('useCommandBar store', () => {
  beforeEach(() => useCommandBar.setState({ open: false, query: '' }))

  it('opens and closes', () => {
    useCommandBar.getState().openBar()
    expect(useCommandBar.getState().open).toBe(true)
    useCommandBar.getState().closeBar()
    expect(useCommandBar.getState().open).toBe(false)
  })

  it('closing clears the query', () => {
    useCommandBar.getState().setQuery('invoices')
    useCommandBar.getState().closeBar()
    expect(useCommandBar.getState().query).toBe('')
  })
})

describe('getResults', () => {
  it('returns ranked, enablement-filtered entries', () => {
    const r = getResults('invoices', [], 5)
    expect(r[0].id).toBe('sales.invoices')
  })
  it('omits disabled-module results', () => {
    const r = getResults('payslips', [], 5) // payroll not enabled
    expect(r.some((e) => e.id === 'payroll.payslips')).toBe(false)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- useCommandBar`
Expected: FAIL — "Failed to resolve import './useCommandBar'".

- [ ] **Step 3: Implement the store + facade**

Create `vousfin-frontend-main/src/features/command-bar/useCommandBar.js`:
```js
import { create } from 'zustand'
import { MODULES } from '@/components/layout/nav.config.js'
import { deriveCatalog } from './catalog'
import { withActions } from './actions'
import { searchCatalog } from './matcher'
import { filterByEnablement } from './filter'

// The catalog is static for the session — build once.
const CATALOG = withActions(deriveCatalog(MODULES))

export function getResults(query, enabledModuleKeys = [], limit = 8) {
  const visible = filterByEnablement(CATALOG, enabledModuleKeys)
  return searchCatalog(visible, query, { limit })
}

export const useCommandBar = create((set) => ({
  open: false,
  query: '',
  openBar: () => set({ open: true }),
  closeBar: () => set({ open: false, query: '' }),
  setQuery: (query) => set({ query }),
}))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- useCommandBar`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/useCommandBar.js src/features/command-bar/useCommandBar.test.js
git commit -m "feat(command-bar): zustand store + memoized result selector"
```

---

### Task 8: Global hotkey hook (⌘/Ctrl+K and `/`)

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/useCommandBarHotkey.js`
- Test: `vousfin-frontend-main/src/features/command-bar/useCommandBarHotkey.test.jsx`

**Interfaces:**
- Consumes: `useCommandBar`.
- Produces: `useCommandBarHotkey()` — a hook that binds `keydown`: `⌘/Ctrl+K` always opens; bare `/` opens only when the user is NOT typing in an input/textarea/contenteditable.

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/useCommandBarHotkey.test.jsx`:
```jsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { useCommandBar } from './useCommandBar'
import { useCommandBarHotkey } from './useCommandBarHotkey'

function Harness() { useCommandBarHotkey(); return <input data-testid="field" /> }

describe('useCommandBarHotkey', () => {
  beforeEach(() => useCommandBar.setState({ open: false, query: '' }))

  it('opens on Ctrl+K', () => {
    render(<Harness />)
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(useCommandBar.getState().open).toBe(true)
  })

  it('opens on bare "/" when not typing in a field', () => {
    render(<Harness />)
    fireEvent.keyDown(window, { key: '/' })
    expect(useCommandBar.getState().open).toBe(true)
  })

  it('does NOT open on "/" while focused in an input', () => {
    const { getByTestId } = render(<Harness />)
    getByTestId('field').focus()
    fireEvent.keyDown(getByTestId('field'), { key: '/' })
    expect(useCommandBar.getState().open).toBe(false)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- useCommandBarHotkey`
Expected: FAIL — "Failed to resolve import './useCommandBarHotkey'".

- [ ] **Step 3: Implement the hook**

Create `vousfin-frontend-main/src/features/command-bar/useCommandBarHotkey.js`:
```js
import { useEffect } from 'react'
import { useCommandBar } from './useCommandBar'

function isTypingTarget(el) {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}

export function useCommandBarHotkey() {
  const openBar = useCommandBar((s) => s.openBar)
  useEffect(() => {
    const onKey = (e) => {
      const cmdK = (e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')
      const slash = e.key === '/' && !isTypingTarget(document.activeElement)
      if (cmdK || slash) {
        e.preventDefault()
        openBar()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openBar])
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- useCommandBarHotkey`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/useCommandBarHotkey.js src/features/command-bar/useCommandBarHotkey.test.jsx
git commit -m "feat(command-bar): global open hotkeys (Cmd/Ctrl+K and /)"
```

---

### Task 9: Accessible CommandBar component

**Files:**
- Create: `vousfin-frontend-main/src/features/command-bar/CommandBar.jsx`
- Test: `vousfin-frontend-main/src/features/command-bar/CommandBar.test.jsx`

**Interfaces:**
- Consumes: `useCommandBar`, `getResults`, `useBusinessStore` (for enabled modules), `useNavigate` (react-router).
- Produces: `<CommandBar />` — a modal dialog implementing the WAI-ARIA combobox pattern: `role="dialog"` + labelled input `role="combobox"` with `aria-expanded`/`aria-controls`/`aria-activedescendant`, a `role="listbox"` of `role="option"` rows grouped by type, an `aria-live="polite"` count region, arrow-key navigation, Enter to navigate, Esc to close.

- [ ] **Step 1: Write the failing test**

Create `vousfin-frontend-main/src/features/command-bar/CommandBar.test.jsx`:
```jsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useCommandBar } from './useCommandBar'

const navigate = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigate,
}))
vi.mock('@/stores/useBusinessStore', () => ({
  useBusinessStore: (sel) => sel({ activeBusiness: { enabledModules: [] } }),
}))

import { CommandBar } from './CommandBar'

const open = () => useCommandBar.setState({ open: true, query: '' })

describe('CommandBar', () => {
  beforeEach(() => { navigate.mockClear(); useCommandBar.setState({ open: false, query: '' }) })

  it('renders an accessible combobox when open', () => {
    open()
    render(<MemoryRouter><CommandBar /></MemoryRouter>)
    const input = screen.getByRole('combobox')
    expect(input).toHaveAttribute('aria-expanded')
  })

  it('shows ranked results and announces the count', () => {
    open()
    render(<MemoryRouter><CommandBar /></MemoryRouter>)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'invoices' } })
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    expect(screen.getByText('Invoices')).toBeInTheDocument()
    expect(screen.getByRole('status').textContent).toMatch(/result/i)
  })

  it('navigates to the top result on Enter', () => {
    open()
    render(<MemoryRouter><CommandBar /></MemoryRouter>)
    const input = screen.getByRole('combobox')
    fireEvent.change(input, { target: { value: 'invoices' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(navigate).toHaveBeenCalledWith('/sales/invoices')
    expect(useCommandBar.getState().open).toBe(false)
  })

  it('closes on Escape', () => {
    open()
    render(<MemoryRouter><CommandBar /></MemoryRouter>)
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Escape' })
    expect(useCommandBar.getState().open).toBe(false)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- CommandBar`
Expected: FAIL — "Failed to resolve import './CommandBar'".

- [ ] **Step 3: Implement the component**

Create `vousfin-frontend-main/src/features/command-bar/CommandBar.jsx`:
```jsx
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useBusinessStore } from '@/stores/useBusinessStore'
import { useCommandBar, getResults } from './useCommandBar'

const GROUP_LABEL = { module: 'Modules', page: 'Pages', action: 'Actions', help: 'Help' }

export function CommandBar() {
  const open = useCommandBar((s) => s.open)
  const query = useCommandBar((s) => s.query)
  const setQuery = useCommandBar((s) => s.setQuery)
  const closeBar = useCommandBar((s) => s.closeBar)
  const enabledModules = useBusinessStore((s) => s.activeBusiness?.enabledModules || [])
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const restoreRef = useRef(null)
  const [active, setActive] = useState(0)

  const results = useMemo(() => getResults(query, enabledModules, 8), [query, enabledModules])

  useEffect(() => { setActive(0) }, [query])
  useEffect(() => {
    if (open) {
      restoreRef.current = document.activeElement
      inputRef.current?.focus()
    } else if (restoreRef.current?.focus) {
      restoreRef.current.focus()
    }
  }, [open])

  if (!open) return null

  const go = (entry) => { if (!entry) return; closeBar(); navigate(entry.href) }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); closeBar() }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); go(results[active]) }
  }

  return (
    <div
      role="dialog" aria-modal="true" aria-label="Search VousFin"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[12vh] motion-reduce:transition-none"
      onMouseDown={(e) => { if (e.target === e.currentTarget) closeBar() }}
    >
      <div className="w-full max-w-xl rounded-xl border border-glass bg-surface shadow-2xl">
        <input
          ref={inputRef}
          role="combobox" aria-expanded={results.length > 0} aria-controls="cmdbar-listbox"
          aria-activedescendant={results[active] ? `cmd-opt-${results[active].id}` : undefined}
          aria-autocomplete="list" aria-label="Search modules, pages and actions"
          className="w-full bg-transparent px-4 py-3 text-base outline-none"
          placeholder="Search VousFin…  (try “who owes me”)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          autoFocus
        />
        <div role="status" aria-live="polite" className="sr-only">
          {query ? `${results.length} result${results.length === 1 ? '' : 's'}` : ''}
        </div>
        {results.length > 0 && (
          <ul role="listbox" id="cmdbar-listbox" className="max-h-[50vh] overflow-y-auto border-t border-glass py-1">
            {results.map((e, i) => {
              const Icon = e.icon
              return (
                <li
                  key={e.id} id={`cmd-opt-${e.id}`} role="option" aria-selected={i === active}
                  className={`flex cursor-pointer items-center gap-3 px-4 py-2 ${i === active ? 'bg-glass' : ''}`}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(ev) => { ev.preventDefault(); go(e) }}
                >
                  {Icon ? <Icon className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" /> : null}
                  <span className="flex-1 truncate">{e.title}</span>
                  <span className="truncate text-xs text-text-muted">{e.path.join(' › ')}</span>
                  <span className="rounded bg-glass px-1.5 py-0.5 text-[10px] uppercase text-text-muted">{GROUP_LABEL[e.type]}</span>
                </li>
              )
            })}
          </ul>
        )}
        {query && results.length === 0 && (
          <div className="border-t border-glass px-4 py-6 text-center text-sm text-text-muted">
            No matches for “{query}”.
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- CommandBar`
Expected: PASS (4). If the business-store mock path differs, align the `vi.mock` path with the real `useBusinessStore` import path used by the component.

- [ ] **Step 5: Commit**

```bash
git add src/features/command-bar/CommandBar.jsx src/features/command-bar/CommandBar.test.jsx
git commit -m "feat(command-bar): accessible WAI-ARIA combobox modal"
```

---

### Task 10: Mount in the app shell + header trigger

**Files:**
- Modify: `vousfin-frontend-main/src/components/layout/DashboardLayout.jsx` (mount `<CommandBar />` + call `useCommandBarHotkey()`; add a header search button)
- Test: manual + the existing build.

**Interfaces:**
- Consumes: `CommandBar`, `useCommandBarHotkey`, `useCommandBar`.

- [ ] **Step 1: Wire the hotkey + modal into the layout**

Open `vousfin-frontend-main/src/components/layout/DashboardLayout.jsx`. Add imports near the other imports:
```jsx
import { CommandBar } from '@/features/command-bar/CommandBar'
import { useCommandBarHotkey } from '@/features/command-bar/useCommandBarHotkey'
import { useCommandBar } from '@/features/command-bar/useCommandBar'
```
Inside the layout component body (with the other hooks), add:
```jsx
  useCommandBarHotkey()
  const openCommandBar = useCommandBar((s) => s.openBar)
```
Render `<CommandBar />` once near the root of the returned JSX (sibling of the main content, e.g. just before the closing wrapper):
```jsx
      <CommandBar />
```

- [ ] **Step 2: Add a visible, accessible header trigger**

In the layout header (next to existing header actions), add a button that opens the bar and advertises the shortcut:
```jsx
      <button
        type="button"
        onClick={openCommandBar}
        aria-keyshortcuts="Control+K"
        className="inline-flex items-center gap-2 rounded-lg border border-glass bg-glass px-3 py-1.5 text-sm text-text-muted"
      >
        <Search className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">Search</span>
        <kbd className="hidden rounded bg-surface px-1.5 text-[10px] sm:inline">⌘K</kbd>
      </button>
```
(Import `Search` from `lucide-react` if not already imported in this file.)

- [ ] **Step 3: Verify the build compiles**

Run: `npm run build`
Expected: build succeeds (the pre-existing chunk-size advisory is fine).

- [ ] **Step 4: Verify in the dev server (preview workflow)**

Start the dev server and confirm: `⌘/Ctrl+K` opens the bar; typing "invoices" shows Invoices; Enter navigates to `/sales/invoices`; Esc closes and returns focus to the trigger. Capture a screenshot for the PR.

- [ ] **Step 5: Run the full frontend test suite + lint**

Run: `npm test && npm run lint`
Expected: all command-bar tests pass; lint clean for the new files.

- [ ] **Step 6: Commit**

```bash
git add src/components/layout/DashboardLayout.jsx
git commit -m "feat(command-bar): mount command bar + header trigger in app shell"
```

---

## Phase 1 Self-Check (run before declaring done)

- [ ] `npm test` green (Tasks 1–9 suites).
- [ ] `npm run build` clean.
- [ ] Keyboard-only pass: open (⌘K and `/`), arrow through results, Enter navigates, Esc restores focus.
- [ ] Screen-reader pass: combobox announced, result count announced via the live region, options readable.
- [ ] Disabled module (e.g. Payroll when off) does not appear in results.

---

## Subsequent Phases (task-level roadmap — expanded to step-level when its predecessor lands)

> These are intentionally NOT broken to single-step granularity yet: their exact code depends on Phase 1's landed shape and the live data. Each becomes its own `docs/superpowers/plans/` file before execution, following the same TDD structure above.

### Phase 2 — Semantic catalog search (backend Tier 2)
- **T1** `VectorDocument` schema: add `scope: 'tenant'|'global'` (default `'tenant'`) + `GLOBAL_CATALOG_BUSINESS_ID` sentinel constant. Tests: existing tenant docs default to `'tenant'`; global docs round-trip.
- **T2** `scripts/reindex-app-catalog.js` (mirror `run-rag-reindex.js`): embed catalog + (Phase 3) help docs into `vectorDocuments` under global scope with `summaryHash` content-skip. Test: re-run is idempotent.
- **T3** `GET /api/v1/search/catalog` controller+service: embed query → `$vectorSearch` global scope → role/enablement filter → ranked entries. Tests: returns only allowed entries; **isolation** — a financial-RAG query never returns `app_catalog` docs and vice-versa.
- **T4** Admin-only `POST /api/v1/admin/search/reindex` (RBAC + `adminMiddleware`, mirrors RAG reindex). Test: non-admin → 403.
- **T5** Frontend escalation: when Tier-1 best score < threshold or query is multi-word NL, call `/search/catalog` (TanStack Query), merge below local results. Test: weak local query triggers the fetch.

### Phase 3 — How-to AI answers (Tier 3) + help corpus
- **T1** `scripts/generate-help-corpus.js`: emit one markdown how-to per module/sub-page from `MODULES` metadata into `content/help/`. Test: every always-on page has a doc; regeneration is content-stable.
- **T2** Index help docs (`dataType:'app_help'`, global scope) via the Phase 2 reindex script.
- **T3** How-to grounding: reuse `modelRouter` + `faithfulnessJudge` over `app_help`; return steps + deep link; refuse on empty retrieval. Tests: grounded answer cites a help source; empty retrieval → refusal (no hallucinated steps).
- **T4** Frontend how-to intent (`/^(how|where|why|can i|what is)\b/i` or an "Ask AI" row) renders the streamed answer with `AssistantMessageMeta` + a "Go to page" deep link.

### Phase 4 — Insight, landing & admin
- **T1** `POST /api/v1/search/log` (hashed query, clicked id, no-result flag; fire-and-forget; no raw PII). Test: logging never blocks/awaits the response path.
- **T2** Admin "Search Insights" tab: top queries, CTR, **no-result backlog**, reindex button + last-run status, help-doc light editor. Tests: aggregations are per-business; reindex button gated to admins.
- **T3** Landing page "Find anything, instantly" feature section + a non-functional animated demo, within `.vf-landing` scope using existing framer-motion/anime.js patterns; `prefers-reduced-motion` respected.
- **T4** Synonym tuning pass driven by real no-result data; final a11y + Urdu/RTL review; expand the relevance test set.

---

## Notes for the implementer

- **Run all frontend commands from `vousfin-frontend-main/`**, backend from `vousfin-backend-main/`.
- **Follow existing patterns:** lazy-loaded pages via `withSuspense()`, errors via `getErrorMessage()`, the single Axios instance in `src/services/api.js`, theme color tokens (`--c-*` / `text-text-muted` / `border-glass`).
- **Never** index per-tenant business data into the catalog scope, and never let a financial-RAG query read global-scope docs — the Phase 2 isolation test is the guard.
- **Commit after every passing step.** If a relevance test fails, fix the data (`synonyms.js`), not the score thresholds.
- **Verify the enabled-modules field name before Task 9/10.** The plan reads enabled modules as `activeBusiness?.enabledModules` (an array of module keys). Open `src/stores/useBusinessStore.js` and confirm the real field; if it differs (e.g. a config object or a different key), adjust the selector in `CommandBar.jsx` and the mock in `CommandBar.test.jsx` to match. The safe default is `[]` (enableable modules stay hidden until wired), so a wrong guess fails closed, never exposing a disabled module.
