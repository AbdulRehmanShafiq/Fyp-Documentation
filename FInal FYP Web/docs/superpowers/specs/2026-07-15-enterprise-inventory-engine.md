# Enterprise Inventory, Sales & Purchase Engine — Audit + Roadmap

**Date:** 2026-07-15 · **Status:** Ratified, implementation started (Phase 0)
**Benchmark set:** QuickBooks Enterprise, NetSuite, SAP Business One, Odoo, Zoho Inventory, Dynamics 365 BC (NAV item-ledger pattern)
**Governing principles:** IAS 2 (cost measurement, lower of cost & NRV), perpetual inventory, matching principle, one accounting engine (CLAUDE.md), documents authoritative → journals immutable projections → reports derived.

---

## 1. Audit — what exists today

### Solid (keep, build on)
- **Item model** with per-item valuation method: `weighted_average` (default) + `fifo` with `costLayers[]` and a pure `consumeFifo` util (tested). Stock floor at 0, insufficient-stock guards, SKU/barcode uniqueness per tenant.
- **Procurement chain**: PO → GRN → Bill with 3-way match (±5%), vendor snapshots, state machines. GRN confirm books **DR Inventory / CR GRNI** at landed unit cost and increments stock idempotently (`inventoryApplied` guard) inside one transaction; cancel reverses GL + stock atomically.
- **Invoice-first sales**: on approval, per-line `reduceStock` (costing-method-aware) then **one consolidated COGS journal** (DR COGS / CR Inventory) in the same session as AR recognition — a COGS failure rolls back revenue (matching principle enforced).
- **Transaction-first sales/purchases**: compound JE gains an auto COGS pair / auto stock increment; deferred side-effects commit with the journal (atomicity F6).
- **R-04 recalc**: journal rewind-replay per item; heals qty/WAC drift with one balanced adjustment JE.
- **Reorder automation**: threshold-crossing detection, low-stock events, automatic vendor reorder email; valuation endpoint; business events (`INVENTORY_RECEIVED/REDUCED/VALUATION_CHANGED/LOW_STOCK`).
- **Ledger substrate**: canonical `journalLines[]`, `postCompoundJournal`/`postBalancedJournal` posters, ledger drift tooling — the accounting rails to build on.

### Defects found (correctness — fix before anything new)
| # | Severity | Finding |
|---|---|---|
| **INV-1** | HIGH | **FIFO COGS mismatch (transaction path).** `transaction.service` step 7 computes the JE's COGS as `qty × unitCostPrice` (WAC) but the deferred `reduceStock` consumes FIFO layers. For FIFO items the posted COGS ≠ subledger reduction → Inventory GL drifts from item valuation on every sale. |
| **INV-2** | HIGH | **Returns don't touch stock.** `creditNote.service` (sales returns) never restocks or reverses COGS; `vendorCredit.service` (purchase returns) never reduces stock. Every goods return silently de-syncs inventory from AR/AP and the GL. |
| **INV-3** | MED | **GRN reversal costed wrong.** Cancel consumes stock via `reduceStock` at *current* WAC / oldest FIFO layers, while the GL reversal restores the *receipt* value. When current cost ≠ receipt cost, subledger ≠ GL after cancel. Receipt reversals must remove the received batch at its receipt cost. |
| **INV-4** | MED | **Recalc corrupts FIFO items.** `replayItem` replays WAC-only and the heal resets qty/WAC but leaves `costLayers` stale → Σlayers ≠ currentStock, next FIFO sale mis-costs. |
| **INV-5** | MED | **Fail-open COGS account resolution.** Accounts resolved by name regex (`/^inventory$/i`, `/cost of goods/i`); a renamed account makes the invoice path *reduce stock then skip the COGS journal* (logged warning → permanent drift) and the transaction path silently skip both. Must resolve by `accountCode` (1150/5110) and fail **closed**. |
| **INV-6** | MED | **No append-only stock movement ledger.** Movement history is inferred from JEs by transaction-type heuristics (INCOME counts as an out; unit cost inferred as amount÷qty). Adjustments, counts, transfers, returns are unrepresentable; point-in-time valuation and item-level audit are approximations. |
| **INV-7** | LOW | Quote-vs-consume race: COGS quoted at build time, consumed at commit; concurrent sales can shift layers between the two (bounded by the double-submit guard; observable once INV-6's ledger exists). |

### Missing capabilities (vs. benchmark set)
Stock adjustments & write-offs (account 6495 exists, no workflow) · physical/cycle counts · multi-warehouse & transfers · landed cost allocation (freight/duty capitalization) · serial/lot + expiry · reservations/ATP/backorders · standard costing + variances · NRV write-downs (IAS 2) · BOM/assembly builds · inventory reports (turnover, aging, margin by item, valuation-as-of-date) · negative-stock policy configuration.

---

## 2. Target architecture (ERP patterns adopted, not invented)

1. **StockMovement — the item sub-ledger** (Dynamics NAV "Item Ledger Entry" pattern). Append-only, tenant-scoped, written in the SAME mongo session as every physical stock change:
   `{ businessId, itemId, warehouseId?, direction: in|out, movementType: purchase|sale|sale_return|purchase_return|receipt_reversal|adjustment|write_off|count|transfer_in|transfer_out|assembly_in|assembly_out, qty, unitCost, value, balanceQtyAfter, balanceValueAfter, source: {docType, docId}, journalEntryId, layersConsumed?, createdBy, at }`.
   Never updated, never deleted — corrections are new movements (mirrors the immutable-JE rule). Item `currentStock/unitCostPrice/costLayers` become **cached projections** rebuildable from movements (same doctrine as account runningBalance).
2. **Costing engine as one pure module** (`inventoryCosting.util`): quote → consume must share one code path so a posted COGS can never diverge from the subledger (fixes INV-1 by construction).
3. **Every movement type maps to a fixed JE recipe** (perpetual inventory):
   - Receipt: DR Inventory 1150 / CR GRNI (doc flow) or CR Cash/AP (direct).
   - Sale: DR COGS 5110 / CR Inventory (at engine cost).
   - Sales return (restock): DR Inventory / CR COGS at original sale cost; refurb/scrap condition → DR Write-off 6495 instead.
   - Purchase return: DR AP (via vendor credit doc) / CR Inventory at receipt cost.
   - Shrinkage/write-off: DR 6495 / CR 1150. Count gain: DR 1150 / CR 6495 (contra usage, plain-labeled "Stock count adjustment").
   - NRV write-down: DR 6495 (or dedicated 5115 "Inventory write-down") / CR 1150; reversal capped at original write-down (IAS 2.33).
   - Landed cost: DR Inventory / CR Landed-Cost Clearing, allocated by value|qty|weight.
   - Transfer: location move, no P&L; optional In-Transit asset account between warehouses.
4. **Reconciliation gate**: `inventoryIntegrity` check — Σ(movement value) per item == item cached valuation, Σ(all items) == Inventory 1150 GL balance; wired into the existing integrity/drift tooling and the Close Cockpit.

---

## 3. Roadmap (strengthen first, then extend)

| Phase | Ships | Accounting treatment | Gate |
|---|---|---|---|
| **0. Correctness hardening** *(this pass)* | Single quote/consume costing path (INV-1); fail-closed account resolution by accountCode w/ regex fallback (INV-5); FIFO-aware replay + layer heal (INV-4); receipt-cost GRN reversal for WAC & FIFO (INV-3) | No new JEs — existing recipes now always self-consistent | All touched suites green; no behavior change for WAC happy path |
| **1. Stock movement ledger** ✅ *shipped 2026-07-15 (e08ebaf)* | StockMovement model + writes at every stock touch; ledger endpoint reads movements (legacy JE inference as fallback, `ledgerSource` marker); `computeDrift`; **opening-balance backfill script** (seeds pre-sub-ledger stock, posts NO journal — the GL already carries it) | none (observability substrate) | ✅ drift reads 0 live after backfill |
| **2. Adjustments + counts** ✅ *shipped 2026-07-15 (3fdaf15 / fe 1ec65fd)* | inventoryAdjustment.service (increase/decrease/write_off/count/revalue + reason codes), NRV write-down w/ IAS 2.33 reversal cap, `POST /inventory/:id/adjust`, plain-language Adjust UI (desktop + phone) | recipes §2.3; every adjustment = movement + JE in one txn; fail-closed on missing 1150/6495 | ✅ 6495 wired; live-verified write-off → drift 0 |
| **3. Returns integration** ✅ *shipped 2026-07-15 (3fdaf15)* | CreditNote lines gain `inventoryItemId` + `restock` (restock at cost, reverse COGS, cancel undoes); VendorCredit gains `returnItems[]` + **Vendor Credit Clearing 1156** (stock out at cost at creation, application drains 1156, cancel restocks) | sale-return / purchase-return recipes | ✅ INV-2 closed — the last known drift source |
| **4. Landed costs** | Landed-cost doc against GRN(s): freight/duty/insurance allocated by value/qty/weight, capitalized into layers/WAC | DR 1150 / CR clearing; bill for freight clears the clearing account | GRN unit cost = PO cost + allocation; margin reports reflect it |
| **5. Warehouses + transfers** | Warehouse model, per-warehouse balances on movements, transfer doc (out+in), default warehouse migration | no P&L; optional in-transit | All flows accept warehouseId; single-warehouse UX unchanged |
| **6. Reservations & fulfillment** | Reserve on invoice/SO draft, ATP = on-hand − reserved, backorder records, fulfillment status | none until ship (then sale recipe) | Overselling blocked by policy, not by error message |
| **7. Serial/lot + expiry** | Lot/serial capture on receipt, consume-by-lot (FEFO option), expiry alerts | costing per lot layer | Traceability report: lot → suppliers → customers |
| **8. Standard costing + variances** | Per-item standard cost; PPV (purchase price variance) + usage variance accounts | DR/CR PPV at receipt; variance close to COGS | Method switch tooling w/ revaluation JE |
| **9. Manufacturing readiness** | BOM, assembly build (consume components → produce FG at rolled-up cost), disassembly | assembly_in/out recipes | Kitting works end-to-end |
| **10. Reporting + AI** | Valuation as-of-date (from movements), turnover, aging, margin by item/category, reorder suggestions from the forecasting service; command-bar answers | derived only — no stored report state | Reports reconcile to 1150 to the cent |

**Standing rules for every phase:** movement + JE post in one `withTransaction`; tenant-scoped queries; plain-language UI copy; tests (normal/edge/concurrency/idempotency/trial-balance); `scripts/ledgerDrift.js` reads 0 after; deletion gate — each phase retires the heuristic it replaces (e.g. Phase 1 deletes the JE-inference stock ledger).

**Architectural decisions taken** (flag if you disagree): (a) item fields stay as cached projections rather than moving reads to the movement table wholesale — matches the account runningBalance doctrine; (b) FIFO layer storage stays embedded on the item (fine ≤ ~200 open layers; revisit if lot tracking explodes cardinality); (c) no separate Sales Order object yet — Invoice drafts carry reservations in Phase 6 (a real SO/DO chain is a later, additive step).
