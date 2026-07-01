# 14 — AI Development Guidelines

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Rules for AI coding agents working in this repository |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> Two audiences: (1) **AI agents that write VousFin's code**, and (2) **VousFin's own product AI** (NL parser, assistant, auto-post). Both must never fabricate accounting or bypass an invariant.

---

## 1. Purpose & scope

Codify how AI participates safely: the mandatory pre-code workflow for coding agents, and the guardrails on the product's own AI features. This operationalizes [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) §11 and [07_SELF_IMPROVEMENT_ENGINE.md](./07_SELF_IMPROVEMENT_ENGINE.md).

---

## Part A — Rules for AI agents writing code

## 2. Mandatory pre-code workflow

Before writing any production code, in order:

1. **Read** the owning spec (Doc 00 §9 ownership map) for the area you touch.
2. **Search** the repository — 126 services, 69 models; the capability often already exists. Don't duplicate a matcher, a poster, or a report.
3. **Understand** the current implementation and its invariants.
4. **Identify** accounting impact, authoritative source, and downstream dependents (reports, events, aging, cache, audit).
5. **Design**; state the journal effect explicitly for accounting changes.
6. **Write a failing test first** (TDD is mandatory for accounting).
7. **Implement** the minimal, general change.
8. **Verify**: full suite + `ledgerDrift` = 0 + build/lint.
9. **Document**: update the owning spec + CHANGELOG.
10. **Commit** per logical change.

Never start coding after reading a single file. Context-gathering is mandatory.

## 3. Hard prohibitions

| # | Never |
|---|---|
| 1 | Create an unbalanced journal entry. |
| 2 | Post to the ledger by any path other than a canonical poster. |
| 3 | Mutate a posted financial field (use reversal). |
| 4 | Special-case one input/customer/report (generalize). |
| 5 | Weaken a test or invariant to make a change pass. |
| 6 | Skip the drift gate. |
| 7 | Bypass tenant scoping. |
| 8 | Add a cache the write path doesn't invalidate. |
| 9 | Introduce a second copy of shared logic (consolidate instead — e.g., account matcher). |
| 10 | Swallow a failure silently. |

## 4. Patterns to reuse (don't reinvent)

| Need | Use |
|---|---|
| Post a system entry | `ledgerPosting.postCompoundJournal` |
| Post a human/AI entry | `transaction.service.createTransaction` |
| Resolve an account name | `utils/accountMatcher.matchAccountByName` |
| Adjust party balance | `partyBalanceService.adjust{Receivable,Payable}` |
| Approval gate | `approval.submitOrPost` |
| Atomic multi-write | `utils/withTransaction` |
| Lifecycle transition | `canTransition` maps in `config/constants.js` |
| Audit | `auditService.log*` |
| Report cache | `utils/reportCache` |

## 5. Course-correction discipline

If you design something that would break an invariant, **stop and verify before shipping**. Precedent: the control-account "posting block" was designed, then rejected after checking `accountFilterRules.js` showed everyday types post to those accounts (Doc 01 §4.4). Record such decisions in the spec + CHANGELOG so they aren't re-attempted.

---

## Part B — Guardrails for the product's AI features

## 6. NL / auto-post pipeline

The product AI (Gemini NL parse, Groq assistant) assists; it never invents accounting.

- **Account resolution.** AI-suggested account names are resolved against the live CoA via `matchAccountByName`; the `accountMapping` confidence reflects **real resolution**, not the LLM's self-report. An unresolved name never posts (EC-AI-01).
- **Tiered confidence policy** (`confidenceCalculator`): ≥98% + **exact** match + business opt-in → auto-post; 95–98% → prefill + require confirm; <95% → clarifying question. Auto-post on a fuzzy match is forbidden regardless of overall score (EC-AI-03).
- **Independent gates.** The amount-threshold approval gate applies on top of confidence — a confident large amount still parks for approval (EC-AI-06).
- **Auto-post is opt-in** (`Business.aiSettings.autoPostEnabled`, default false), tagged `transactionSource=ai_auto_posted`, fully reversible, and surfaced for passive review.
- **Excel import** enforces per-row confidence: High imports, Medium flags, Low is held back (EC-IMPORT-01..03).
- **AI Decision Ledger (Intelligence Roadmap Phase 0, shipped 2026-07-01).** Every AI action must call `aiDecision.service.record(businessId, kind, payload)` at decision time and `recordOutcome(decisionId, businessId, outcome)` when the user accepts/corrects/reverses it. The `AIDecision` collection (`models/AIDecision.model.js`) is append-only (immutability hooks block bulk update/delete) and the service never throws into the caller — a logging failure can never break or slow an AI/accounting path. The NL-parse + auto-post path (`transaction.controller.js`) is the reference instrumentation; other AI paths (Excel classify, bill match, bank reconcile, anomaly, forecast) follow the same two-call pattern in later phases. Read surface: `GET /api/v1/ai-decisions` (gated by `ai:review`).

## 7. RAG / retrieval

- Tenant vs global isolation via `VectorDocument.scope` + `GLOBAL_CATALOG_BUSINESS_ID`; tenant queries never retrieve another tenant's vectors.
- Embedding dimensions must match across index and query (a 3072-vs-768 mismatch once broke retrieval — pin `outputDimensionality=768` + normalize).
- Grounded answers only: the assistant answers from retrieved tenant data; it refuses or falls back rather than fabricating figures.

## 8. AI is advisory on accounting

Anomaly detection, forecasting, and the assistant are **read-only** with respect to the ledger. They classify, predict, explain, and recommend; they never create or mutate journal entries directly. Any AI-proposed action becomes a `ProposedAction`/`PendingTransaction` behind the approval + integrity gates.

## 9. Business rules

| ID | Rule |
|---|---|
| AI-01 | AI never fabricates a ledger record; unresolved accounts don't post. |
| AI-02 | Confidence uses real CoA resolution, not LLM self-report. |
| AI-03 | Auto-post requires opt-in + ≥98% + exact match; amount gate still applies. |
| AI-04 | RAG is tenant-isolated and dimension-consistent. |
| AI-05 | AI accounting suggestions are advisory; posting goes through the pipeline + gates. |
| AI-06 | Coding agents follow the pre-code workflow and hard prohibitions. |

## 10. Acceptance criteria

- [ ] An AI parse with an unresolved account never posts.
- [ ] Auto-post fires only with opt-in + ≥98% + exact match; blocked on fuzzy.
- [ ] A large-amount confident parse still parks for approval.
- [ ] RAG returns only the tenant's own vectors.
- [ ] A coding-agent change ships with a failing-first test, drift 0, and a CHANGELOG entry.

## 11. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| AI invents account | Trusting LLM name | Resolve + refuse (AI-01) |
| Over-eager auto-post | Trusting overall score on fuzzy match | Exact-match gate (AI-03) |
| Cross-tenant retrieval | Missing scope filter | Scope + sentinel (AI-04) |
| Agent duplicates logic | No repo search | Pre-code search (step 2) |

## 12. Regression / 13. Implementation guidance

AI-feature changes are tested on the deterministic pipeline (confidence, resolution, gates) with the provider mocked. Coding-agent changes follow Docs 10 + 13. When in doubt about accounting impact, consult Doc 01 and ask before shipping.

## 14. Cross references

[00_MASTER_PLAN.md](./00_MASTER_PLAN.md) §11 · [01_ACCOUNTING_ENGINE_SPECIFICATION.md](./01_ACCOUNTING_ENGINE_SPECIFICATION.md) · [07_SELF_IMPROVEMENT_ENGINE.md](./07_SELF_IMPROVEMENT_ENGINE.md) · [08_EDGE_CASE_LIBRARY.md](./08_EDGE_CASE_LIBRARY.md)

## 15. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from shipped AI pipeline (confidence tiers, resolution, RAG isolation) + coding-agent workflow. |

## 16. Progress checklist

- [x] Coding-agent pre-code workflow + prohibitions
- [x] Product-AI guardrails (confidence, resolution, RAG, advisory-only)
- [x] Reuse map to avoid duplication
- [ ] Agent-proposed-fix flow behind approval (future)
