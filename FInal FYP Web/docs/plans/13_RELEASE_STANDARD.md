# 13 — Release Standard

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Definition of done, release gates, checklist |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> A change ships only when it is correct, tested, balanced, documented, and reversible. "It works on my machine" is not done. The trial balance and drift gate are hard blockers.

---

## 1. Purpose & scope

Define the objective bar every change must clear before merge/deploy, and the mechanics of a release. Applies to both repos (backend + frontend). Complements [10_TESTING_STRATEGY.md](./10_TESTING_STRATEGY.md) (test taxonomy) and [14_AI_DEVELOPMENT_GUIDELINES.md](./14_AI_DEVELOPMENT_GUIDELINES.md) (workflow).

## 2. Definition of done

A change is done only when ALL hold:

1. Business rules implemented per the owning spec.
2. Input validation present.
3. Accounting correct: every entry balances; correct legs per [04](./04_TRANSACTION_LIFECYCLE.md).
4. Inventory correct; stock reconciles to GL 1150 where touched.
5. Reports, aging, party balances, and caches update correctly.
6. Unit + integration tests green; new behaviour is TDD'd; each bug has a locking regression test.
7. **Ledger drift = 0** (`node scripts/ledgerDrift.js`).
8. Integrity gate green (`npm run test:integrity`) for accounting changes.
9. Frontend build + lint clean (where frontend touched); Vitest green.
10. Security considered: authZ, tenant scope, audit logging, no secret leakage.
11. Error handling complete; failures surfaced, never silently swallowed.
12. Edge cases from [08](./08_EDGE_CASE_LIBRARY.md) covered for the touched area.
13. Owning spec + [CHANGELOG.md](./CHANGELOG.md) updated.
14. Change integrates with the rest of the system (no regressions in adjacent areas).

## 3. Release gates (blocking)

| Gate | Command | Blocks release if |
|---|---|---|
| Test suite | `npm test` | Any failure |
| Drift | `node scripts/ledgerDrift.js` | drift ≠ 0 or unbalanced |
| Integrity | `npm run test:integrity` | Any VE check red |
| Frontend | `npx vitest run` + `npm run build` + lint | Any failure |
| Docs | manual | Owning spec/CHANGELOG not updated |

## 4. Change classification

| Class | Extra requirements |
|---|---|
| Accounting-affecting | TDD mandatory; drift + integrity gates; balanced-JE + reversal tests; spec update |
| Schema/migration | Idempotent migration + migration test; drift re-verify; Doc 02 update |
| Security | RBAC/SoD/isolation tests; Doc 12 update |
| Report | Reconciliation test; cache-invalidation test; Doc 09 update |
| Frontend-only | Build + lint + Vitest; no backend gates |
| Docs-only | CHANGELOG entry |

## 5. Commit & branch discipline

- One logical change per commit; scoped diffs; descriptive messages.
- Never bundle unrelated changes.
- Commit/push only when the work is complete and gated (per project workflow).
- Never skip hooks or bypass signing.
- Co-authorship trailer on commits per repo convention.

## 6. Versioning & CHANGELOG

- Documentation changes are recorded in [CHANGELOG.md](./CHANGELOG.md) with date, doc, and summary.
- Semantic intent: MAJOR for invariant/architecture change, MINOR for additive capability, PATCH for corrections.

## 7. Deployment

- Backend: Vercel serverless (auto-deploy on push to `main`, ~40s). `app.js` exports the app; `server.js` (listen + cron) is not used on serverless — jobs run via cron-job.org.
- Frontend: Vercel SPA (auto-deploy on push).
- Post-deploy smoke: `/health` responds; a representative report renders; drift script (run against prod read-only) shows 0.

## 8. Business rules

| ID | Rule |
|---|---|
| RS-01 | No merge without green suite + drift 0. |
| RS-02 | Accounting changes require TDD + integrity gate. |
| RS-03 | Every change updates its owning spec + CHANGELOG. |
| RS-04 | Never weaken a gate to ship. |
| RS-05 | Reversibility: shipped features must be reversible (feature flag or reversal path). |

## 9. Acceptance criteria (release readiness)

- [ ] All gates in §3 green.
- [ ] Definition-of-done items §2 all satisfied.
- [ ] CHANGELOG + owning spec updated.
- [ ] Post-deploy smoke passes; prod drift 0.

## 10. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Regression shipped | Skipped gate | Mandatory gates (RS-01) |
| Silent drift in prod | No drift check | Drift gate + post-deploy check |
| Undocumented behaviour | Skipped docs | RS-03 |
| Un-reversible feature | No flag/reversal | RS-05 |

## 11. Regression / 12. Implementation guidance

Run gates locally before pushing. For accounting changes, run `ledgerDrift` after every phase. Keep the release small; prefer several gated commits over one large one.

## 13. Known gaps

Gates are enforced by discipline, not yet CI-automated (see [10](./10_TESTING_STRATEGY.md) §12). Wiring drift + integrity + suite into CI is the top release-engineering task.

## 14. Cross references

[10_TESTING_STRATEGY.md](./10_TESTING_STRATEGY.md) · [06_VALIDATION_ENGINE.md](./06_VALIDATION_ENGINE.md) · [14_AI_DEVELOPMENT_GUIDELINES.md](./14_AI_DEVELOPMENT_GUIDELINES.md)

## 15. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from real gates/scripts/deploy; records CI-automation gap. |

## 16. Progress checklist

- [x] Definition of done
- [x] Blocking gates + change classification
- [x] Deploy + smoke procedure
- [ ] CI automation of gates
