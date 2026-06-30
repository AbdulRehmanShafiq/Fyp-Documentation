# VousFin Command Bar — Intelligent Module Search (Design Spec)

**Date:** 2026-06-30
**Status:** Approved direction, ready for implementation plan
**Author:** Brainstormed with the user; supersedes the generic `deep-research-report (3).md`

---

## 1. Summary

A single, accessible **command bar** (open with `Ctrl/⌘+K` or `/`) that lets any user find and jump to **anything in VousFin by meaning** — modules, sub-pages, settings, quick actions ("New Invoice"), and how-to help — even when they don't know the exact menu path.

It is built by **reusing VousFin's existing infrastructure**, not by adding the new stack the research report proposed. VousFin already has every capability the report wanted to buy:

| Report proposed | VousFin already has |
|---|---|
| Weaviate / Qdrant / Pinecone | Atlas `$vectorSearch` on `vectorDocuments` (+ local-cosine fallback) |
| OpenAI embeddings | `embeddingService` — Gemini `gemini-embedding-001` 768-dim + deterministic local fallback (card-free) |
| Separate hybrid search service | `ragQuery.service` — already merges vector + keyword and reranks |
| Manual route harvesting | `nav.config.js` `MODULES` — already a structured catalog |
| Celery / Kubernetes workers | Deploy-time scripts + the existing cron-job.org trigger pattern |

This keeps the feature **card-free**, serverless-friendly, and consistent with the platform.

---

## 2. Goals

- **Navigation:** "where is X?" → one keystroke to the right page.
- **Productivity:** power users reach any page/action without the mouse.
- **Onboarding & self-service:** "how do I reconcile a payment?" → a grounded, step-by-step answer with a deep link.
- **Accessibility:** the fastest, most inclusive way to operate VousFin — fully keyboard- and screen-reader-operable, WCAG 2.1 AA, RTL/Urdu-ready.
- **Insight:** every search (and every *failed* search) becomes a signal that improves the product.

## 3. Non-goals / scope boundaries

- **Not** indexing per-tenant business data (invoices, customers) for search — that is the *financial RAG assistant's* job and stays separate. The command bar searches the **application**, not the ledger.
- **Not** a new vector database, embedding provider, or background-worker infrastructure.
- **Not** authoring a large hand-written help corpus up front — the seed corpus is auto-generated, then refined incrementally.

---

## 4. Architecture — three tiers, fastest-first

Each tier only escalates when the previous one is weak, so the common case is instant and the expensive paths (embeddings, LLM) run only when they add value. This is the card-free, quota-respecting core.

```
 user types ──▶ Tier 1: instant local match (0ms, offline)
                   │  strong exact/prefix/synonym hit? ──▶ show
                   │  weak / natural-language query?
                   ▼
                Tier 2: semantic catalog search (backend $vectorSearch)
                   │  "billing statement" → Invoices, "who owes me" → AR aging
                   ▼
                Tier 3: how-to AI answer (explicit "how do I…")
                      grounded in the help corpus → steps + deep link
```

### Tier 1 — Instant local index (no network)
- A **static index** built at frontend build time from the catalog (§5). Shipped in the bundle.
- A **hand-rolled, zero-dependency matcher**: normalized exact > prefix > token > synonym/tag > subsequence (fuzzy), with a transparent scoring function we can tune and test.
- Filtered **client-side** by the user's role and the business's enabled modules (`useAuthStore`, `useBusinessStore`).
- Handles ~80% of queries (known module/page/action names) with zero latency, works offline.

### Tier 2 — Semantic catalog search (backend)
- Triggered when Tier 1's best score is below a threshold, or the query is multi-word natural language.
- `GET /api/v1/search/catalog?q=…&role=…&modules=…` → embed query (`embeddingService`) → `$vectorSearch` over **global catalog vectors** (§7) → role/enablement filter → ranked entries.
- Reuses the exact graceful-degradation path the RAG pipeline already has (Atlas → local cosine → keyword).

### Tier 3 — How-to AI answer
- Triggered by explicit how-to intent (query matches `/^(how|where|why|can i|what is)\b/i` or a "Ask AI" affordance).
- Grounds an answer in the **auto-generated help corpus** (§6) via `modelRouter` + `faithfulnessJudge`, returning concise steps **plus a deep link** to the destination page. Refuses (no hallucinated steps) when retrieval is empty.
- Reuses the existing assistant streaming + `AssistantMessageMeta` (sources/confidence) UI.

---

## 5. The catalog — single source of truth

### 5.1 Module/page entries
`nav.config.js` `MODULES` is already the authoritative navigation catalog. A **pure derivation** function flattens it into searchable entries — no second source to keep in sync.

```js
// derived catalog entry
{
  id: 'sales.invoices.recurring',     // stable id
  type: 'module' | 'page' | 'action' | 'help',
  title: 'Recurring Invoices',
  path: ['Sales', 'Invoices', 'Recurring'],   // breadcrumb
  href: '/sales/invoices/recurring',
  icon: 'Repeat',                     // lucide name
  synonyms: ['recurring', 'subscription', 'auto invoice', 'billing schedule'],
  roles: ['accountant', 'manager'],   // who can see it (null = all)
  moduleKey: 'sales',                 // for enablement filtering
  enablementKey: null,                // e.g. 'payroll' for enableable modules
}
```

### 5.2 Quick actions
A small declarative `actions.catalog.js` (e.g. `New Invoice → /sales/invoices/new`, `Record Payment`, `Add Customer`). Where possible, seeded from `primary: true` items already in `MODULES`.

### 5.3 Synonyms
A curated `synonyms.map.js` (accounting-term ↔ plain-word, e.g. *receivables ↔ "who owes me"*, *payables ↔ "what I owe"*). Aligns with the platform rule that user-facing copy is plain-language for non-accountants. This file is the primary tuning lever for relevance.

---

## 6. Help corpus (auto-generated seed)

A generator produces one concise **how-to doc per module/sub-page** from existing metadata (`name`, `subtitle`, `tag`, breadcrumb, primary actions):

```md
---
id: help.sales.invoices.recurring
title: How to set up recurring invoices
href: /sales/invoices/recurring
module: sales
---
Recurring invoices bill a customer automatically on a schedule.
1. Open **Sales → Invoices → Recurring**.
2. Choose a customer and a template.
3. Set the frequency and start date, then save.
```

- Stored as version-controlled markdown/JSON under `vousfin-backend-main/content/help/` — editable; hand-refine the high-traffic ones over time.
- Regenerating is idempotent (content-hash skip). The **Admin "Search Insights"** tab (§11) surfaces *no-result queries* as a prioritized content-gap backlog so authoring effort goes where users actually struggle.

---

## 7. Multi-tenancy & vector scope (the report's key correction)

VousFin's modules are **identical across all tenants** — only *enablement* and *roles* differ. Therefore the catalog/help vectors are **global**, indexed **once**, not per-tenant. This is the deliberate opposite of the financial RAG (which is strictly per-tenant) and the two must never cross.

- **Storage:** reuse `vectorDocuments` with `dataType: 'app_catalog' | 'app_help'` and a reserved global scope.
- **Schema:** add a `scope: 'tenant' | 'global'` field (default `'tenant'`); global catalog docs use a reserved sentinel `businessId` (`GLOBAL_CATALOG_BUSINESS_ID`) so the existing required-`businessId` index and tenant-isolation post-filter stay intact. The financial RAG query path keeps its mandatory real-`businessId` prefilter, so it can **never** read global docs and vice-versa.
- **Query-time filtering:** by **role + enabled modules** (from the caller's session), *not* by tenant. The same catalog serves everyone; the client only ever sees entries it's allowed to.

This avoids re-embedding the same ~80-entry catalog 1000× per tenant and keeps cost ≈ a single small reindex.

---

## 8. Indexing pipeline (no runtime worker)

- **Tier-1 static index:** emitted by a frontend build script (`scripts/build-search-index.mjs`) → a JSON asset imported by the command bar. Pure, deterministic, no DB.
- **Tier-2/3 vectors:** a backend script `scripts/reindex-app-catalog.js` (mirrors the `run-rag-reindex.js` pattern shipped this session) embeds catalog + help docs into `vectorDocuments` under the global scope, with `summaryHash` content-skip so only changed entries re-embed. Run on deploy (and on-demand from Admin) via the existing cron/admin-trigger pattern — fail-closed on missing secret.

---

## 9. Backend API

- `GET /api/v1/search/catalog?q=&limit=` — Tier-2 semantic search over global catalog; auth required; role/enablement derived from the session; returns `{ results:[{id,type,title,path,href,icon,score}], tookMs, mode }`.
- **How-to** reuses the existing assistant stream with a `scope: 'howto'` flag (grounded in `app_help`), rather than a parallel endpoint.
- `POST /api/v1/search/log` — fire-and-forget analytics event (query hash, result-clicked id, no-result flag); never blocks the response. No raw PII (see §13).
- `POST /api/v1/admin/search/reindex` — admin-only (RBAC + `adminMiddleware`, mirrors the RAG reindex route) → runs the catalog reindex.

All endpoints return the standard `ApiResponse` shape and use `ApiError` for failures.

---

## 10. Frontend — the command bar

- One `CommandBar` component mounted at the app shell; opened by `Ctrl/⌘+K` or `/` (ignored while typing in inputs), and by a header search affordance.
- **200ms debounce.** Tier-1 results render instantly as the user types; Tier-2/3 stream in for natural-language / how-to queries.
- **Grouped results:** Modules · Pages · Actions · Help, each with icon + breadcrumb; matched terms highlighted.
- **Deep-linking + actions:** Enter navigates (or triggers the action); how-to answers render inline with a "Go to page" deep link and the existing sources/confidence chips.
- State via a small Zustand store (`useCommandBarStore`); data via TanStack Query (cache hot queries; the report's "Redis hot-query cache" is unnecessary at this scale).

---

## 11. Accessibility (first-class — WCAG 2.1 AA)

The command bar is the single biggest "makes VousFin easy" lever, so accessibility is in the core, not a later phase. It implements the **WAI-ARIA combobox + listbox** pattern:

- **Keyboard:** `↑/↓` move, `Enter` selects, `Esc` closes, `Tab` cycles result groups, `Home/End` jump; the trigger hint ("Press / or ⌘K to search") is announced and visible.
- **Screen readers:** `role="combobox"` input with `aria-expanded`, `aria-controls`, `aria-activedescendant`; results in `role="listbox"`/`role="option"`; a polite `aria-live` region announces result counts ("8 results") and "no results".
- **Focus management:** focus trap inside the modal; focus restored to the invoking element on close; visible focus rings honoring the theme tokens.
- **Motion & contrast:** respects `prefers-reduced-motion`; all states meet 4.5:1 contrast across the four design themes; never relies on color alone (icons + text labels).
- **RTL / i18n:** layout and keyboard semantics work in Urdu/RTL; all strings go through the existing i18n layer.
- **Targets:** 44×44px touch targets on mobile; works in the mobile nav sheet.

A11y is verified with automated checks (axe) plus a keyboard-only and screen-reader pass in the test plan (§14).

---

## 12. Landing page updates

Market the command bar as a headline capability (it differentiates VousFin as "the accountant's OS you can drive by typing"):

- A **feature section** ("Find anything, instantly") within the existing `.vf-landing` scope, using the established framer-motion/anime.js patterns — no new heavy deps.
- A lightweight, **non-functional interactive demo** (a faux command bar that animates a query → result) so visitors *feel* the speed. Reduced-motion respected.
- A one-line mention in the hero/feature grid; consistent with the existing landing design language and themes.

## 13. Admin page updates — "Search Insights"

A new tab in the existing Admin page turns search into a product-improvement loop:

- **Top queries** and **click-through rate** (which searches lead to a navigation).
- **No-result / low-confidence queries** → the prioritized **content-gap backlog** that drives help-corpus authoring and synonym tuning.
- **Reindex control:** a button to trigger `POST /admin/search/reindex` with last-run status (mirrors how the RAG reindex is operated).
- **Help-content editor (read + light edit):** view/edit the generated help docs for the highest-gap topics.
- All admin-only (RBAC), tenant-aware where relevant (analytics are per-business; the catalog itself is global).

## 14. Analytics & privacy

- Log only: a **hashed query**, matched intent/tier, the clicked result id, and a no-result flag — never the raw query text tied to a user (consistent with the AI assistant's hash-only logging). Aggregations power §13.
- Fire-and-forget; never blocks search. Respects the platform's append-only audit philosophy for any state it writes.

## 15. Testing strategy

- **Unit:** catalog derivation (`MODULES` → entries, stable ids); the Tier-1 matcher (a labeled `query → expected-id` table per persona); role + enablement filtering; synonym expansion; help-doc generation idempotency.
- **Backend:** catalog reindex (global scope, content-skip); `/search/catalog` returns only role/enablement-allowed entries; **global vs tenant isolation** (a financial-RAG query must never return `app_catalog` docs and vice-versa); how-to grounding + refusal on empty retrieval.
- **Frontend/E2E:** open via hotkey, type → results, Enter navigates to the right route; how-to renders steps + deep link.
- **Accessibility:** automated axe checks + a documented keyboard-only and screen-reader pass; reduced-motion and RTL snapshots.
- **Relevance regression:** the labeled per-persona query set computes precision@5 on every change (guards against tuning regressions).

## 16. Performance & card-free constraints

- Tier 1 is instant and offline. Tier 2 runs only on weak/NL queries (bounded embedding calls; respects the free Gemini quota with the local fallback already in place). Tier 3 runs only on explicit how-to.
- No new infra, no always-on worker, no paid service. Scales trivially — the catalog is ~80–200 docs, not "millions of vectors."

---

## 17. Phasing / milestones

- **P1 — Command bar + Tier 1 (ships ~80% of the value alone):** catalog derivation, quick-actions + synonyms, hand-rolled matcher, the accessible `CommandBar` modal, role/enablement filtering, hotkeys, deep-linking. Full a11y from day one.
- **P2 — Tier 2 semantic:** `scope` schema field + global sentinel, `reindex-app-catalog` script, `/search/catalog` endpoint, isolation tests, frontend escalation.
- **P3 — Tier 3 how-to:** help-corpus generator + seed content, how-to grounding via `modelRouter`/`faithfulnessJudge`, inline answer UI with deep link + sources.
- **P4 — Insight & polish:** analytics logging, Admin "Search Insights" tab, Landing feature section + demo, synonym tuning from no-result data, final a11y/Urdu/RTL pass.

## 18. Success criteria

- ≥80% of top-5 results relevant on the labeled set; p95 Tier-1 latency ~0ms, Tier-2 < 300ms.
- <1% of valid-intent queries return no results (tracked and driven down via §13).
- Command bar fully operable by keyboard and screen reader (axe clean, manual pass signed off).
- No regression to the financial RAG, ledger, or drift (the catalog path is isolated and read-only w.r.t. business data).

## 19. Risks & mitigations

- **Help-corpus quality (auto-generated):** seed is shallow → mitigated by the no-result backlog driving targeted hand-refinement.
- **Global/tenant vector mix-up:** mitigated by the `scope` field + sentinel + explicit isolation tests on both query paths.
- **Free Gemini quota for reindex:** the catalog is tiny and embedded once; local fallback covers quota exhaustion (both index and query degrade together, staying consistent).
- **Concurrency on reindex:** content-hash skip + admin-only trigger make re-runs safe and idempotent.

---

## 20. Out of scope (explicit)

Per-tenant document search, a hand-written help encyclopedia, Redis hot-query caching, cross-encoder/self-hosted rerankers, and any paid vector DB or embedding API — all unnecessary at this scale and incompatible with the card-free constraint.
