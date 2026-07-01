# 12 — Security & Audit

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | AuthN/Z, RBAC, SoD, audit trail, retention, compliance, data protection |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> Every financial action is authenticated, authorized, tenant-isolated, and audited with before/after state. Security controls are layered and independent — no single check is the only line of defence.

---

## 1. Purpose & scope

Specify the security and audit architecture: request hardening, authentication, authorization (RBAC + SoD), tenant isolation, the audit trail, retention, compliance tooling, and data protection. Sites: `app.js` middleware chain, `middleware/*`, `config/passport.js`, `services/{audit,sod,internalAudit,retention,compliance,amlScreening,mfa}.service.js`.

## 2. Request pipeline hardening (`app.js`, in order)

1. `helmet()` — security headers.
2. `cors({...})` — configured origins.
3. `compression()`.
4. `express.json({limit:'10mb'})` + `urlencoded({limit:'10mb'})`.
5. `cookieParser()`.
6. `passport.initialize()` — JWT strategy.
7. `morgan('combined')` → logger.
8. `sanitizeRequest()` (mongo-sanitize) — strips operator injection.
9. `defaultLimiter` on `/api` — rate limiting.
10. `/api/v1` routes.
11. 404 handler → global `errorMiddleware`.

## 3. Authentication

- **JWT** via Passport (`auth.middleware`). Tokens carry `user.id`, `businessId`, `role`.
- **Logout** blacklists the JWT (`User.tokenBlacklist`, checked per request).
- **OAuth** optional Google sign-in (`authProvider`).
- **MFA** TOTP (`mfa.service`): `mfa.secret`/`backupCodes` stored `select:false`; 5-minute challenge token; backup codes single-use.
- **Email verification** for new signups; idle-logout (15 min) on the frontend.

## 4. Authorization

- **RBAC** (`rbac.middleware`, `middleware/admin.middleware`, `procurementPermissions`): role/permission checks per route (`requireRole('admin')`, procurement permissions). `Role`/`Permission`/`Membership` models back team access.
- **Business context** (`business.middleware`): binds the request to the user's tenant; blocks access without a business.
- **Segregation of Duties (SoD)** (`sod.service`, `SodRule`): enforces conflicting-duty rules (e.g., submitter ≠ approver when `allowSelfApproval=false`), backing the approval workflow.
- **Approval workflow** (`approval.service`): amount-threshold gate parks large transactions; independent of AI confidence gate.

**Known gap (flagged).** The 3-way-match override route is not yet role-gated (`requireRole('admin')` pending) — see §12.

## 5. Tenant isolation

- Every query is `businessId`-scoped (Master Plan I7). Journal-line account IDs are validated to belong to the tenant before posting (prevents cross-tenant balance corruption).
- RAG isolation via `VectorDocument.scope` + `GLOBAL_CATALOG_BUSINESS_ID` sentinel.
- Isolation is covered by dedicated tests (Atlas post-filter isolation test, RBAC enforcement test).

## 6. Audit trail

- `AuditLog` is **append-only** (schema hooks throw on update/delete): `entityType`, `entityId`, `action`, `performedBy`, `performedByName`, `beforeState`, `afterState`, `ipAddress`, `timestamp`. Every financial mutation logs who/when/why/before/after (Master Plan explainability).
- `EventLog` records the append-only business-event stream; `internalAudit.service` + `AuditPlan`/`AuditFinding` support internal audit workflows; `procurementAudit.service` logs procurement actions.
- Answers: who performed it, when, why, which records changed, previous state, what caused it.

## 7. Retention & compliance

- `RetentionPolicy` + `retention.service` govern data-retention windows (financial history is preserved; only non-financial ancillary data is aged per policy).
- `compliance.service` + `ComplianceObligation`, `amlScreening.service` + `CounterpartyScreening` (AML/sanctions), `taxReport`/`returnFiling` for statutory filing. `complianceReminder.job` schedules obligations.

## 8. Data protection

- Sensitive fields excluded from responses: `passwordHash`, `tokenBlacklist`, `verificationToken`, `mfa.secret`, `mfa.backupCodes`, `embedding` (via `select:false` / `toJSON` transforms).
- Passwords bcrypt-hashed; MFA secrets never returned.
- Least-privilege DB user; network allow-list on Atlas.
- Secrets in environment variables, not code.

## 9. Business rules

| ID | Rule |
|---|---|
| SEC-01 | Every financial action is authenticated, authorized, tenant-scoped, and audited. |
| SEC-02 | Audit and event logs are immutable (insert-only). |
| SEC-03 | SoD prevents a single actor from both submitting and approving when disallowed. |
| SEC-04 | Sensitive fields never leave the server. |
| SEC-05 | Approval (amount) and confidence (AI) gates are independent layers. |
| SEC-06 | Journal-line accounts are validated against the tenant before posting. |
| SEC-07 | Least privilege for DB, roles, and network. |

## 10. Acceptance criteria

- [ ] An unauthenticated request to a financial route returns 401.
- [ ] A role without permission returns 403 (RBAC test).
- [ ] Submitter cannot approve own transaction when `allowSelfApproval=false` (SoD test).
- [ ] Updating an `AuditLog` throws.
- [ ] A cross-tenant id in a request is rejected (isolation test).
- [ ] MFA secret is absent from any API response.

## 11. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Privilege escalation | Missing role gate | RBAC middleware; §12 gap tracked |
| Cross-tenant access | Missing `businessId` filter | Tenant scoping + tests |
| Injection | Operator payload | mongo-sanitize |
| Secret leakage | Field returned | `select:false`/`toJSON` |
| Repudiation | No audit record | Mandatory audit-log on mutations |

## 12. Known security TODOs (flagged, from audit)

- **Rotate exposed Atlas DB password** and update `MONGO_URI` (a live password was pasted into chat historically).
- **Role-gate the 3-way-match override** route (`requireRole('admin')`).
- **Wire the integrity gate into CI** (currently manual) so tampering that causes drift is caught automatically.
- Free-tier gaps: no error tracking / log aggregation / uptime monitoring; Brevo sender on a freemail domain (deliverability/SPF-DKIM-DMARC risk). Enterprise-grade requires paid infra.

## 13. Regression / 14. Implementation guidance

Security-affecting changes ship with RBAC/SoD/isolation tests. Add new privileged routes behind the appropriate role/permission middleware; log every financial mutation via `auditService`; never bypass the tenant scope.

## 15. Future expansion

Field-level encryption for the most sensitive data, key management, SSO/SAML for enterprise, immutable off-site audit export, and continuous compliance monitoring.

## 16. Cross references

[02_DATABASE_ARCHITECTURE.md](./02_DATABASE_ARCHITECTURE.md) · [06_VALIDATION_ENGINE.md](./06_VALIDATION_ENGINE.md) · [08_EDGE_CASE_LIBRARY.md](./08_EDGE_CASE_LIBRARY.md) · [13_RELEASE_STANDARD.md](./13_RELEASE_STANDARD.md)

## 17. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from real middleware chain, RBAC/SoD/audit services; records flagged security TODOs. |

## 18. Progress checklist

- [x] Middleware chain + auth/MFA
- [x] RBAC + SoD + tenant isolation
- [x] Audit/retention/compliance
- [x] Flagged TODOs (DB pw rotation, override gate, CI integrity)
- [ ] Field-level encryption + SSO (future)
