# 11 — Performance & Scalability

| | |
|---|---|
| **Status** | Living / Authoritative |
| **Version** | 2.0.0 |
| **Owner of** | Indexing, caching, concurrency, bulk paths, scale roadmap |
| **Last updated** | 2026-07-01 |
| **Parent** | [00_MASTER_PLAN.md](./00_MASTER_PLAN.md) |

> Correctness first, then performance. Optimize only after correctness is proven, and never in a way that risks an invariant. Prefer incremental updates, caching, aggregation, and background jobs over recomputation.

---

## 1. Purpose & scope

Specify the performance architecture (indexes, cache, concurrency, bulk paths) and the path to larger scale. Current production is a card-free free tier (Vercel serverless + Atlas M0) — the dominant latency source is infra, not code; this document separates the two.

## 2. Current performance architecture

| Concern | Mechanism | Site |
|---|---|---|
| Query selectivity | `businessId`-leading compound indexes on every collection | schemas |
| Read acceleration | `reportCache` (Map + optional Redis), TTL 30s–5min, invalidated on write | `utils/reportCache.js` |
| Report math | Aggregation `$group` over effective lines, not per-row loops | report services |
| Read shape | `.lean()` + field projection | repositories |
| Pagination | On all list endpoints | controllers |
| Balance updates | Atomic `$inc`, O(lines) | `updateRunningBalance` |
| Bulk posting | Bounded concurrency + sequential recovery pass | `batchPosting.service` |
| Serverless warmth | `minPoolSize:1` warm Atlas socket, `maxPoolSize:10` | `config/database.js` |
| FE cache | TanStack Query (`gcTime` 30min, `keepPreviousData`) | `src/App.jsx`, hooks |
| Background work | `node-cron` (local) / cron-job.org (serverless) for reminders, recognition, recurring, CFO, trend, forecasting | `server.js`, `jobs/` |

## 3. Concurrency & bulk import

- **Atomic balance updates** avoid read-modify-write races (`$inc`).
- **Multi-doc transactions** (`withTransaction`) keep JE + balances consistent; Mongo retries transient WriteConflicts.
- **Bulk import** posts with bounded concurrency (`BATCH_POST_CONCURRENCY`, default 8) then a **sequential recovery pass** for rows that lost a WriteConflict (retried single-threaded with a stable idempotency key). On Atlas M0, per-row multi-doc transactions are the inherent bulk-import cost; the recovery pass fixes correctness (no skips), not raw throughput. True bulk speed needs an aggregated single-transaction poster (net delta per account) or paid infra (§7).

## 4. Cache invalidation contract

Every ledger write invalidates `reportCache` for the tenant within the same request cycle, so no stale total survives a write. Business events additionally invalidate analytics caches and (debounced ~5 min) reindex RAG vectors. Cache is a projection: correctness never depends on it.

## 5. Known cost hotspots

| Hotspot | Note | Mitigation |
|---|---|---|
| Vercel cold starts (~10–30s intermittent) | Dominant perceived lag | Keep-warm ping to `/health` (DB-free, warms Mongo); paid Pro keeps functions warm |
| Atlas M0 latency | Shared free tier | Warm pool; M10+ for real throughput |
| Bulk import on M0 | Per-row txn | Recovery pass (correctness); aggregated poster (future) |
| `useTransactions` `INFINITE_PAGE_SIZE` | Large page fetches | Lower page size if list feels heavy |
| Forecasting/CFO packs | Heavy compute | Run on cron, cache output |

## 6. Business rules

| ID | Rule |
|---|---|
| PF-01 | Never trade an invariant for speed. |
| PF-02 | Every new query has a `businessId`-leading index. |
| PF-03 | Reports use aggregation + cache, never per-row app loops. |
| PF-04 | Bulk paths use bounded concurrency + recovery pass. |
| PF-05 | Cache is invalidated on every write; correctness independent of cache. |
| PF-06 | Optimize only after profiling shows a real bottleneck. |

## 7. Scale roadmap

| Stage | Change |
|---|---|
| Now | Free tier; warm pool; cache; recovery pass |
| Keep-warm | cron-job.org ping `/health` every ~5 min to kill cold starts |
| Paid infra | Vercel Pro (warm functions) + Atlas M10+ (throughput, backups) |
| Aggregated poster | Single-transaction bulk poster (net balance delta per account) for fast large imports |
| Horizontal | Shard by `businessId`; read replicas for reporting |
| Analytics tier | Event-stream-fed analytics store; archival tiering of aged journals |
| 100M journal lines | Time-partitioned collections + incremental report materialization + watermark-based validation |

## 8. Acceptance criteria

- [ ] Every list/report endpoint is paginated and index-backed.
- [ ] A 100k-entry dataset (Doc 05) reports within target and drift = 0.
- [ ] Cache invalidation verified by a write-then-read test.
- [ ] Bulk import of a large file records all valid rows (no silent skips) via the recovery pass.

## 9. Failure modes

| Failure | Cause | Mitigation |
|---|---|---|
| Slow first request | Cold start | Keep-warm ping |
| Report timeout at volume | Missing index / app-loop | Aggregation + index (PF-02/03) |
| Bulk import slow/partial | M0 per-row txn | Recovery pass; aggregated poster |
| Memory growth | Unbounded cache | `MAX_ENTRIES` cap + TTL |

## 10. Regression / 11. Implementation guidance

Profile before optimizing. Add the index with the query. Keep report math in aggregation. When adding a bulk path, reuse `batchPosting` semantics (concurrency + recovery). Never introduce a cache the write path doesn't invalidate.

## 12. Security notes

Rate limiting (`/api` default limiter) protects against abuse; keep-warm pings hit only the DB-free `/health`. See Doc 12.

## 13. Cross references

[02_DATABASE_ARCHITECTURE.md](./02_DATABASE_ARCHITECTURE.md) · [04_TRANSACTION_LIFECYCLE.md](./04_TRANSACTION_LIFECYCLE.md) · [09_REPORTING_ENGINE.md](./09_REPORTING_ENGINE.md)

## 14. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-07-01 | Authored from real caching/concurrency/infra; records free-tier hotspots + scale path. |

## 15. Progress checklist

- [x] Index/cache/concurrency architecture
- [x] Bulk-import recovery pass documented
- [x] Free-tier hotspots + scale roadmap
- [ ] Aggregated single-transaction poster (future)
- [ ] Keep-warm ping wired in ops
