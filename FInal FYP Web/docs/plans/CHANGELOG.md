# CHANGELOG — docs/plans specification suite

All changes to the VousFin engineering specification suite are recorded here, newest first. Format: date · document(s) · summary. Every future documentation change MUST add an entry. Versioning intent: MAJOR = invariant/architecture change, MINOR = additive capability, PATCH = correction.

---

## 2026-07-01 — Suite v2.0.0 (initial ratified suite)

Authored the full 16-document suite from a complete, read-only repository audit (69 models, 126 services, 68 route files, 14 background jobs, 217 unit + 8 integration tests). Replaces an earlier inaccurate 1.0 draft.

| Doc | Version | Change |
|---|---|---|
| 00_MASTER_PLAN | 2.0.0 | **Rewrote.** Corrected the business-domain framing from a mobile-repair ERP to a general SME accounting platform (repair/technician/IMEI/warehouse/branch are explicitly NOT modelled). Added invariant table (I1–I10), module map, ownership/conflict-resolution map, mandatory workflow. Fixed broken escaped-markdown. |
| 01_ACCOUNTING_ENGINE_SPECIFICATION | 2.0.0 | **Rewrote.** Grounded in real posters (`postCompoundJournal`/`postBalancedJournal`/`createTransaction`), tax-engine functions + R-03 clamp, IAS 21 FX, period control, reversal, `computeDrift`. Recorded the control-account "posting block" **rejected-design** decision. Fixed broken markdown. |
| 02_DATABASE_ARCHITECTURE | 2.0.0 | **Rewrote.** Real ownership/source-of-truth map, index catalog (JournalEntry/CoA/documents), multi-doc transaction + WriteConflict recovery model, migration inventory + rules. Fixed broken markdown. |
| 03_BUSINESS_DOMAIN_MODEL | 2.0.0 | **Authored** (was empty). All entity clusters from the 69-model audit; explicit "NOT modelled" table to prevent phantom features; state-machine rule; domain-wide rules + acceptance criteria. |
| 04_TRANSACTION_LIFECYCLE | 2.0.0 | **Authored.** Universal 12-stage pipeline; all entry channels; full transaction catalog with real account codes/legs; Excel import + sequential recovery pass; downstream propagation + rollback. |
| 05_DATASET_GENERATOR_SPECIFICATION | 1.0.0 | **Authored.** Pipeline-faithful synthetic-data design; volumes (100k+ JEs, 5000 customers, etc.); CSV + SQL portable formats; coverage matrix. Generator not yet built. |
| 06_VALIDATION_ENGINE | 1.0.0 | **Authored.** VE-1…VE-15 invariant catalog; write-time vs post-hoc split; unified harness design extending `run-integrity-gate.js`. |
| 07_SELF_IMPROVEMENT_ENGINE | 1.0.0 | **Authored.** Scenario→fail→root-cause→fix→regress loop with guardrails (no hard-coded fixes, TDD, root-cause) and a root-cause taxonomy mapped to shipped fixes. |
| 08_EDGE_CASE_LIBRARY | 1.0.0 | **Authored.** ~90 edge cases across 17 areas with required behaviours (REJECT/BLOCK/ADJUST/ALLOW+FLAG/ALLOW). Records EC-CONTROL-01 (control accounts remain directly postable). |
| 09_REPORTING_ENGINE | 2.0.0 | **Authored.** Every report from real routes/services; derive-don't-store principle; each report tied to a Validation-Engine reconcile check. |
| 10_TESTING_STRATEGY | 2.0.0 | **Authored.** Real suite taxonomy (Jest 217 unit + 8 integration; Vitest FE), gates (drift/integrity), TDD mandate, Vitest reporter gotcha, CI-automation gap. |
| 11_PERFORMANCE_AND_SCALABILITY | 2.0.0 | **Authored.** Index/cache/concurrency architecture; free-tier hotspots (cold starts, M0); bulk-import recovery pass; scale roadmap to aggregated poster + sharding. |
| 12_SECURITY_AND_AUDIT | 2.0.0 | **Authored.** Real middleware chain, JWT/MFA/OAuth, RBAC + SoD, tenant isolation, append-only audit, retention/compliance; flagged TODOs (rotate DB pw, gate 3-way override, CI integrity). |
| 13_RELEASE_STANDARD | 2.0.0 | **Authored.** Definition of done, blocking gates, change classification, deploy/smoke, CI-automation gap. |
| 14_AI_DEVELOPMENT_GUIDELINES | 2.0.0 | **Authored.** Coding-agent pre-code workflow + hard prohibitions + reuse map; product-AI guardrails (real-resolution confidence, tiered auto-post, RAG isolation, advisory-only accounting). |
| CHANGELOG | — | Created. |

### Context

This suite was commissioned to become the permanent engineering constitution of the repository. The earlier draft `00`–`02` mis-described VousFin as a mobile-sales/repair/accessories ERP and rendered as escaped markdown; on the user's instruction those were overwritten with audit-grounded content. All 16 documents cross-reference each other via the ownership map in 00 §9.

### Known open items captured across the suite

- Wire drift + integrity gates into CI (Docs 06, 10, 13).
- Build the dataset generator + verifier (Doc 05).
- Aggregated single-transaction bulk poster for fast large imports (Docs 04, 11) — explicitly deferred by the user pending a future database/deployment infrastructure upgrade.
- ~~Rotate exposed Atlas DB password~~ — done (user rotated it directly, 2026-07-01). ~~Role-gate the 3-way-match override~~ — done (`match:override` permission, backend `98ec65a`).
- ~~Control-vs-subledger reconcile checks VE-5/VE-6~~ — done (`ledgerIntegrity.computeArApSubledgerDrift`, backend `51315df`).
- ~~Scheduled batch fixed-asset depreciation~~ — done (`fixedAssetDepreciation.job`, daily cron, backend `d02af22`).

---

## 2026-07-02 — Import account resolution overhaul + Phases 5 & 6 cores

**Bulk-import "account not found" fix (reported: Owner Equity rows rejected).** Root cause: the seeded chart has no account named "Owner Equity" (equity defaults are 3110 Capital / Investment, 3120 Distributions / Drawings, …) and the name matcher had no path from vernacular names to standard accounts. Shipped the enterprise resolution chain, fully deterministic (no LLM guessing):
1. `utils/importAccountResolver.js` — **code matching** ("3110", "3110 - Capital"), a curated **bookkeeping-synonym table** (Owner Equity/Owner's Capital→3110, Debtors→1110, Creditors→2110, Sales Revenue→4110, ~120 entries), **keyword+transaction-type account-shape inference**, and **standard code allocation** (next free code in the type's 1xxx–6xxx range).
2. `services/importAccountResolution.service.js` — resolve-or-create: when a row names an account that truly doesn't exist, it is **created automatically** with the inferred type/subtype/normal balance, the next standard code, `autoCreated: true` (new ChartOfAccount field), an audit-log entry, and batch-level dedupe + duplicate-key race recovery. Junk names (too short/numeric-only) never become accounts.
3. Wired into `uploadExcelPreview` (unknown accounts are "will be created" rows — flagged Medium, not errors) and `confirmExcelImport` (creates, counts, reports `createdAccounts`).
4. **CoA visibility:** the Excel template now includes a live "Chart of Accounts" sheet (code/name/type/group) and the frontend Chart of Accounts page now shows the reference **Code** column + an "added automatically during import" badge.

**Phase 5 core (multi-modal ingestion lineage).** The bookkeeper document pipeline (`ingest` — photo/text → Gemini read → policy-gated proposal) now records a `classify` decision in the AI Decision Ledger (inputs, candidates, confidence, linked SourceDocument) and marks it `accepted` when policy auto-executes the post.

**Phase 6 core (unified brain).** `services/brainContext.service.js` + `GET /autonomy/brain-context` — one tenant-scoped, fault-isolated read surface aggregating the learned-preference store, measured calibration, STP scorecard, close readiness, and health, so every agent reasons from the same picture. Derivation-only; stores nothing.

Verification: 251 suites/1786 tests green (+31 TDD tests), `npm run eval` PASS, production ledger drift 0 across all 4 businesses. Frontend: 75 tests green, build clean.

---

## 2026-07-02 — Continuous Close & STP + Proactive AI CFO (Intelligence Roadmap Phases 3 & 4)

| Doc | Version | Change |
|---|---|---|
| 14_AI_DEVELOPMENT_GUIDELINES | 2.3.0 | Documented the STP scorecard, close-readiness score, and the advisor feed (ledger-recorded recommendations). |

**Phase 3 — Continuous Close & STP.** `utils/stpMetrics.helper.js` + `services/stpScorecard.service.js` — the straight-through-processing scorecard: windowed per-tenant automation rates for posting (`ai_auto_posted` vs user-originated JEs), matching (clean 3-way matches), reconciliation (auto-matched bank lines), and categorization (accepted AI decisions); capabilities with no activity report null, never a false 0%. `utils/closeReadiness.helper.js` + `services/closeReadiness.service.js` — a weighted close-readiness checklist over the existing engines (due recognitions, due depreciation, pending approvals, unmatched bank lines, ledger drift, AI review queue); a failing data source reads "not verified" (blocks), never a false pass, and `ready` requires every check green regardless of score. Endpoints: `GET /autonomy/stp-scorecard`, `GET /autonomy/close/readiness`. Continuous reconciliation jobs and the orchestrated close itself already existed (`bankReconciliation.job`, `closeAgent`) and were reused, not rebuilt.

**Phase 4 — Proactive AI CFO.** `utils/advisor.helper.js` (pure, grounded-by-construction recommendation builder — every "why" cites only numbers passed in) + `services/advisor.service.js` (fault-isolated signal gathering from the 13-week cash forecast, AR aging, business health, and the STP scorecard) + `GET /advisor/recommendations`. Ranked critical→info: projected cash dip, chase 60+-day receivables, weak health score, low automation. Every non-empty advisory run is recorded in the AI Decision Ledger (kind `recommend`) — advice has the same lineage as every other AI action. Framing stays "here's what your numbers say" (not investment advice). Deferred to follow-ons: conversational what-if, benchmark-driven advice, frontend surfaces.

Verification: 248 suites/1755 tests green (+32 TDD tests), `npm run eval` PASS, production ledger drift 0 across all 4 businesses (both features are read-only derivations — they can never disagree with the ledger).

---

## 2026-07-01 — Closed Learning Loop + Explainability (Intelligence Roadmap Phases 1 & 2)

| Doc | Version | Change |
|---|---|---|
| 14_AI_DEVELOPMENT_GUIDELINES | 2.2.0 | Documented the Phase 1 learning loop (learned description→accounts resolution ahead of fuzzy; conservative-only confidence recalibration) and Phase 2 explainability (grounded, faithful-by-construction explanations; one-click correct/reverse that feeds learning). |

**Phase 1 — Closed Learning Loop.** `utils/learningKey.helper.js` (normalize a description to a stable per-tenant key), `services/learnedResolution.service.js` (learn/recall description→accounts over the existing `EntityMemory` store, kind `nl_description_accounts`, never-throwing), `utils/aiCalibration.helper.js` + `services/aiCalibration.service.js` (measured acceptance/reversal rates from the Phase-0 ledger → a **conservative-only** effective auto-post threshold, never below the 0.98 floor), plus a new `aiDecision.repository.outcomeBreakdown`. Wired into `transaction.controller.js`: recall beats fuzzy in `processNaturalLanguage`; the final confirmed/auto-posted mapping is learned. Read surface `GET /api/v1/ai-decisions/stats`.

**Phase 2 — Explainability Everywhere.** `utils/aiExplain.helper.js` (deterministic, faithful-by-construction plain-language explanation) + `services/aiExplain.service.js`; endpoints `GET /api/v1/ai-decisions/:id/explain`, `POST /api/v1/ai-decisions/:id/outcome` (accept/correct/reverse — a correction feeds Phase 1 learning), all `ai:review`-gated.

Guardrails held: a learned mapping never overrides an explicit user choice; recalibration only tightens, never loosens; explanations reference only stored values; the ledger is untouched (this work only observes/advises). TDD throughout (44 new backend tests). Full suite 240 suites/1723 tests green; `npm run eval` PASS (10/10); production ledger drift unchanged at 0 across all 4 businesses. See `docs/superpowers/specs/2026-07-01-vousfin-intelligence-roadmap-design.md` (Phases 1 & 2 marked shipped).

---

## 2026-07-01 — AI Decision Ledger + Evaluation Harness (Intelligence Roadmap Phase 0)

| Doc | Version | Change |
|---|---|---|
| 06_VALIDATION_ENGINE | 1.1.0 | Added `npm run eval` as the AI model/prompt regression gate (§4), generalizing the forecasting champion/challenger discipline to every AI capability. |
| 14_AI_DEVELOPMENT_GUIDELINES | 2.1.0 | Documented the mandatory `aiDecision.service.record()` / `recordOutcome()` instrumentation contract for every AI decision point (§6). |

Shipped: `models/AIDecision.model.js` (append-only lineage collection), `utils/aiDecision.helper.js` (pure record-builder + outcome-transition guard), `repositories/aiDecision.repository.js`, `services/aiDecision.service.js` (never-throwing), `GET /api/v1/ai-decisions` (`ai:review`-gated read surface), reference instrumentation on the NL-parse + auto-post path (`transaction.controller.js`), and `scripts/eval/runEval.js` (`npm run eval`) scoring the NL type-mapping layer against a golden set with a baseline-regression gate. TDD throughout (36 new backend tests); full suite 233 suites/1679 tests green; `npm run eval` PASS (10/10); production ledger drift unchanged at 0 across all 4 businesses (this phase only observes AI decisions — it never posts). Backend HEAD to follow this entry's commit. See `docs/superpowers/specs/2026-07-01-vousfin-intelligence-roadmap-design.md` (roadmap) and `docs/superpowers/plans/2026-07-01-phase0-ai-decision-ledger.md` (implementation plan).

---

## Template for future entries

```
## YYYY-MM-DD — <short title>

| Doc | Version | Change |
|---|---|---|
| <NN_DOC> | x.y.z | <what changed and why> |

<Optional context / decisions / links to commits>
```
