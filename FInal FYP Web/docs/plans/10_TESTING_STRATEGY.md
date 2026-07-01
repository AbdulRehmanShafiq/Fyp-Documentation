# 10 — Testing Strategy

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Test taxonomy, gates, coverage expectations |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> No accounting feature is complete without tests. TDD is mandatory for accounting-affecting changes. The trial balance and drift gate are release blockers.

---

## 1. Purpose & scope

Define how VousFin is tested end to end and which gates block release. Current state (backend): **Jest**, ~217 unit test files under `tests/unit/{config,controllers,jobs,middleware,models,nlParser,repositories,services,utils,validations}` and 8 integration suites under `tests/integration/{api,erp,...}`. Frontend: **Vitest** (command-bar, public pages, utils; ~75 tests). Scripts: `npm test`, `test:unit`, `test:integration`, `test:coverage`, `test:integrity` (`run-integrity-gate.js`), `test:api`.

## 2. Test taxonomy

| Layer | Purpose | Where | Runner |
|---|---|---|---|
| **Unit** | Pure functions, services (mocked repos/models), validators | `tests/unit/**` | Jest |
| **Integration** | Multi-service flows against a DB (PO→GRN→Bill, payroll, RBAC, budget, cost) | `tests/integration/**` | Jest |
| **Accounting tests** | Balanced JE, drift, reversal netting, tax/FX legs | unit + integration | Jest |
| **Regression** | Every fixed bug has a locking test | throughout | Jest |
| **Integrity gate** | Drift = 0, statements reconcile | `scripts/run-integrity-gate.js`, `scripts/ledgerDrift.js` | Node |
| **API tests** | Endpoint contracts | `tests/integration/api`, `scripts/test-all-apis.js` | Jest/Node |
| **Security tests** | RBAC, SoD, tenant isolation | `rbac.enforcement.test.js`, isolation tests | Jest |
| **Frontend** | Components, hooks, utils | `src/**/*.test.js(x)` | Vitest |
| **Performance/stress** | Volume + concurrency (planned, via generator) | `scripts/` | Node |
| **Mutation** | Test-suite adequacy (planned) | — | (future) |
| **E2E / acceptance** | User journeys (planned) | — | (future) |

## 3. TDD discipline (mandatory for accounting)

Red → Green → Refactor. Write a failing test that reproduces the requirement/bug, watch it fail for the right reason, write the minimal code to pass, keep the suite green. Never write accounting production code before a failing test. This is the same discipline the recent CoA/confidence work followed (each phase: RED→GREEN, full suite + drift = 0).

## 4. What every accounting test must assert

Per [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) testing requirements:
- Normal flow produces the exact documented journal legs ([04](./04_TRANSACTION_LIFECYCLE.md)).
- Edge cases from [08](./08_EDGE_CASE_LIBRARY.md) behave as specified.
- Concurrency safety (idempotency, recovery pass) where relevant.
- Idempotency (retried request doesn't double-post).
- Historical integrity (immutability, period lock).
- Financial correctness: Σdebit = Σcredit; drift unchanged/zero.
- Trial-balance validation on the affected dataset.
- Regression prevention (bug reproduced first).

## 5. Gates (release blockers)

| Gate | Command | Pass condition |
|---|---|---|
| Unit + integration | `npm test` | All green |
| Ledger drift | `node scripts/ledgerDrift.js` | `worst drift 0, any unbalanced: false` |
| Integrity gate | `npm run test:integrity` | All VE checks green |
| Frontend | `npx vitest run` | All green |
| Build/lint | `npm run build` / lint | Clean (frontend); backend has no lint config |

**Vitest gotcha (frontend).** The default reporter can hang when a full-suite run is backgrounded by a harness; run with `--reporter=json --outputFile=<path>` and parse the JSON (`--reporter=basic` was removed in Vitest 4).

## 6. Coverage expectations

- Accounting core (`transaction`, `ledgerPosting`, `journalGenerator`, `taxEngine`, `ledgerIntegrity`, `partyBalance`, `installment`, `invoice`, `bill`, `payment`): high line + branch coverage; every journal path tested.
- New pure utilities: exhaustive (exact/fuzzy/ambiguous/none for matchers; boundary values for calculators).
- `test:coverage` produces the report; treat uncovered accounting branches as defects.

## 7. Business rules

| ID | Rule |
|---|---|
| TS-01 | Accounting changes are TDD; failing test first. |
| TS-02 | Every fixed bug ships with a locking regression test. |
| TS-03 | Drift gate must read 0 before merge/release. |
| TS-04 | Never weaken a test or invariant to pass a change. |
| TS-05 | Integration tests exercise real multi-service flows, not mocks-only. |
| TS-06 | Tenant-isolation and RBAC have dedicated tests. |

## 8. Acceptance criteria

- [ ] Full backend suite green (`npm test`).
- [ ] `ledgerDrift.js` prints drift 0 across all businesses.
- [ ] Integrity gate green.
- [ ] Frontend Vitest suite green; build + lint clean.
- [ ] Each new accounting path has a balanced-JE + reversal test.

## 9. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Flaky integration tests | Shared DB state / open handles | `--forceExit --detectOpenHandles`; isolated fixtures |
| Green suite, real drift | Missing drift assertion | Mandatory drift gate (TS-03) |
| Overfit tests | Testing the mock, not behaviour | Prefer real code paths (TS-05) |
| Vitest hang | Default reporter backgrounded | JSON reporter workaround (§5) |

## 10. Regression requirements

The suite is the living regression contract. CI must run all gates; today the drift/integrity gates are **manual** — wiring them into CI is the top testing gap (see §12).

## 11. Implementation guidance

Place unit tests beside their subject's category folder; mock only external boundaries (DB, network, AI providers). Integration tests use a real (test) Mongo. Reuse existing fixtures/helpers. For AI/NLP, mock the provider and assert on the deterministic pipeline (confidence, resolution, gates), not the LLM output.

## 12. Known gaps

- CI does not yet run `ledgerDrift`/`run-integrity-gate` automatically (manual today).
- No mutation testing, load/stress harness, or E2E browser tests yet (planned; depend on the dataset generator, Doc 05).
- Backend has no ESLint config (frontend does).

## 13. Performance / 14. Security notes

Stress/concurrency tests (planned) validate the recovery pass and index performance at volume. Security tests cover RBAC, SoD, tenant isolation, JWT blacklist, and injection sanitization. See Doc 11/12.

## 15. Cross references

[06_VALIDATION_ENGINE.md](./06_VALIDATION_ENGINE.md) · [07_SELF_IMPROVEMENT_ENGINE.md](./07_SELF_IMPROVEMENT_ENGINE.md) · [08_EDGE_CASE_LIBRARY.md](./08_EDGE_CASE_LIBRARY.md) · [13_RELEASE_STANDARD.md](./13_RELEASE_STANDARD.md)

## 16. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from real suite (217 unit + 8 integration), scripts, and gates; records Vitest gotcha and CI gap. |

## 17. Progress checklist

- [x] Taxonomy + gates from real config
- [x] TDD mandate + accounting assertions
- [x] Known gaps recorded
- [ ] Drift/integrity gates in CI
- [ ] Mutation + load + E2E harnesses
