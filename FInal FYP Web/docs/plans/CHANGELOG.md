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
