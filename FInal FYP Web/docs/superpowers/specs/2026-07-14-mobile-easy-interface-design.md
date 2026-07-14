# Mobile Easy — VousFin on a Phone, Complete and Effortless

- **Date:** 2026-07-14
- **Status:** Draft for user review (planning only — no code in this pass)
- **Scope:** `vousfin-frontend-main/` phone experience (<768px). Builds on the shipped mobile kit (Sheet · ListCard · SwipeRow · PullToRefresh · MobilePage · bottom nav), the easy-mode copy program, the photo-receipt spec (2026-07-13), and the Ledger design system (phases 0–10, all shipped).
- **The bar:** a shop owner who has never seen accounting software can do **everything they need** from their phone — record money, send an invoice, chase payment, check where they stand, approve what's waiting — each in **under 3 taps from Home**, with plain words, one obvious action per screen.

---

## 1. Principles (every screen obeys all six)

1. **One job per screen.** A phone screen answers one question or does one task. Anything second-priority is one tap deeper, never beside.
2. **The 3-tap rule.** The five daily jobs (record · invoice · chase · check · approve) each complete in ≤3 taps from Home. If a flow needs more, the flow is wrong, not the user.
3. **Thumb-first.** The primary action always lives in the bottom third (sticky CTA or bottom bar). Nothing essential is top-right only. Targets ≥48px, gaps ≥8px.
4. **Plain words, always.** Owner language is the interface ("Who owes me", "Record something", "Money left"); accounting terms appear only as quiet secondary hints. All new copy through i18n keys (Urdu fills per screen).
5. **Sheets over pages.** If the user needs to keep their place, the task opens as a bottom sheet (kit `Sheet`); full navigation only when the context truly changes. Every sheet: drag handle, safe-area padding, sticky footer action.
6. **Capture over forms.** The phone's superpower is the camera and the keyboard's first row. Photo → AI, or one plain sentence → parsed entry (both engines already exist: photo-receipt spec + NL smart entry). Typing into field grids is the fallback, never the default.

**What we deliberately do NOT do:** no separate mobile app, no hamburger-only nav, no desktop grids squeezed down, no feature removal ("everything he wants" = full capability, arranged for one hand), no new color/typography (Ledger tokens as-is).

---

## 2. Where mobile stands today (audit)

**Working well (keep):**
- Bottom tab bar (`MobileNav`): Home · Reports · ⊕ Create · AI · Menu — with raised ⊕.
- Purpose-built screens: `MobileHome`, `MobileTransactions`, `MobileInvoices`, `MobileBills`, `MobileOutstanding`, `MobileInventory` (pull-to-refresh, swipe actions, sticky CTAs).
- `Modal` renders as a full-height sheet on phones — every dialog inherits it.
- **New since phase 2:** every SmartTable list collapses to ListCards under 768px — so the ~90 pages without a bespoke fork now degrade *gracefully* instead of horizontally scrolling.
- Simple entry mode (six plain chips + natural-language line) is the default create experience.

**Gaps this spec closes:**
- G1 — The bottom bar's second tab is **Reports**, but the second most frequent phone job is **seeing who owes you / chasing** (money, not statements).
- G2 — **Capture is buried**: ⊕ opens the form modal; photo-receipt (specced) and voice aren't first-class; no "capture now, finish later" queue.
- G3 — **Approvals/review on the go** — the accountant's phone job — has no purpose-built surface (desktop queue collapses, but cards are dense and the j/k keys don't exist on touch).
- G4 — **Editors** (invoice/bill) on phones are long desktop forms in disguise; no step-by-step flow; Save requires scrolling to reach.
- G5 — **Reports on phone** are shrunken statements; no glanceable "statement as cards" reading mode; period control is desktop chrome.
- G6 — Sheet flows lack a consistent **sticky footer action** (the form's submit sits at the end of the scroll).
- G7 — No **haptic/feedback vocabulary**; success is a toast that may sit under the thumb.
- G8 — Menu sheet duplicates nav definitions instead of deriving fully from `nav.config`.

---

## 3. Mobile IA — the five tabs

**Bottom bar (revised):**

```
┌──────────────────────────────────────────────┐
│   Home    Money     (⊕)     Ask      Menu    │
│  Today   in & out  Capture   AI    everything│
└──────────────────────────────────────────────┘
```

| Tab | Job | Contents |
|---|---|---|
| **Home** | "Am I OK? What needs me?" | Cash hero · needs-you chips · this month · recent (existing `MobileHome`, upgraded §4.1) |
| **Money** *(replaces Reports tab)* | "Who owes me / what do I owe / what happened" | Segmented: **Owed to me · I owe · All activity** — the three money lists, chase actions inline. Statements live behind a "Reports" row here and in Menu (G1) |
| **⊕ Capture** | "Record what just happened" | The capture sheet (§4.2): photo · say/type a sentence · quick chips |
| **Ask** | "Ask anything / find anything" | Existing command-bar surface, full-screen on phones |
| **Menu** | Everything else | Module list generated from `nav.config` (G8) + Inbox badge + Settings |

- **Inbox (approvals + AI queue + exceptions)** surfaces as a **badge on Menu** and a pinned first row inside it, plus the needs-you chips on Home — matching the notification model on desktop.
- Deep links preserved: every desktop route still renders (SmartTable cards guarantee a readable fallback), so nothing is phone-unreachable.

---

## 4. Screen-by-screen design

### 4.1 Home (Today) — upgrade, not rebuild

```
Good evening, Abdul            FinTech Solutions
┌────────────────────────────────────────────┐
│ CASH ON HAND ⓘ                             │
│ Rs 70.9M                                    │
│ ● Healthy · money across your accounts      │
└────────────────────────────────────────────┘
[ 3 things need you → ]        (chip, only when >0)
┌───────────────┐  ┌───────────────┐
│ Came in       │  │ Went out      │
│ +Rs 118,000   │  │ −Rs 96,100    │
└───────────────┘  └───────────────┘
RECENT ————————————————————————————
▸ Sold Infinix Hot 60i      +Rs 55,000
▸ Fuel                       −Rs 4,500
▸ Kamran the plumber         −Rs 8,000
              [ ⊕ Record something ]   ← sticky
```

Changes from today's `MobileHome`: the ⓘ **Explain** popover joins the cash hero (parity with desktop); "things need you" chip counts approvals + review queue + exceptions (same sources as the desktop bell); role-aware order (staff see the needs-you chip block *above* the hero, same rule as desktop). Everything else stays.

### 4.2 Capture sheet (⊕) — the heart of mobile

One sheet, three lanes, opened from any tab:

```
╭──────────── drag handle ────────────╮
│  Record something                    │
│                                      │
│  ┌────────────────────────────────┐  │
│  │  📷  Snap a receipt            │  │  ← camera → photo-receipt
│  └────────────────────────────────┘  │     pipeline (2026-07-13 spec)
│  ┌────────────────────────────────┐  │
│  │  Say it or type it…            │  │  ← NL line → smart entry
│  └────────────────────────────────┘  │     parser (shipped)
│   sold 3 phones 45000 cash  ← ghost  │
│                                      │
│  OR PICK ONE                         │
│  [Got paid] [Paid someone] [Sold]    │  ← the six simple chips
│  [Bought]  [Owed to me] [I owe]      │
│                                      │
│  ├ sticky footer ──────────────────┤ │
│  │        [ Review & save ]        │ │
╰──────────────────────────────────────╯
```

- **Photo lane:** camera → upload → AI extraction → a *confirmation card* (amount, who, what, account) with one **Save** button. If offline/slow: "Saved to your queue — we'll finish it when you're back" (capture-now-finish-later queue, G2; drafts land in the existing AI review queue so nothing bypasses the pipeline).
- **Sentence lane:** the shipped NL parser; the parse preview renders as the same confirmation card. Voice = the OS keyboard's mic (no custom speech stack in v1).
- **Chips lane:** existing simple mode, restyled into the sheet.
- Every lane ends at the **same confirmation card** → one mental model. Detailed mode remains one tap away ("More options") for accountants — power is deeper, never removed.

### 4.3 Money tab

Segmented control (Owed to me · I owe · Activity), each a ListCard list:

- **Owed to me:** customer + amount + how overdue ("14 days late" in words, not aging buckets). Swipe right → **Remind** (send reminder), swipe left → **Record payment** (sheet). Tap → customer sheet with balance history + the same two buttons big.
- **I owe:** mirrored for bills (Pay / See bill).
- **Activity:** existing `MobileTransactions` moves here unchanged.
- Header row: two quiet totals ("You're owed Rs X · You owe Rs Y") + a "Reports →" row at the bottom for statements (§4.6).

**Chase in ≤3 taps:** Money → swipe → Remind. Done.

### 4.4 Send an invoice in under a minute (G4)

Replace the collapsed desktop editor with a **3-step sheet flow** (each step one question, sticky Next):

```
Step 1  WHO         customer picker (recent first, big rows,
                    "+ New customer" inline — name+phone only)
Step 2  WHAT        line items as cards: item picker or free text,
                    qty stepper, price. [+ Add another]
                    Running total pinned under the header.
Step 3  SEND        due date chips (Today · 7d · 30d · custom),
                    preview card, [ Send invoice ] (primary) /
                    [ Save draft ] (ghost)
```

- Powered by the same draft/create hooks the desktop editor uses — the flow is a *renderer*, not a new pipeline (accounting path identical).
- Discounts, tax overrides, currency, bank details live under one "More options" disclosure per step — visible defaults come from the business profile and tax engine, so most users never open it.
- Bills get the same flow with "Who" = supplier, plus the photo lane shortcut ("Snap the bill instead").

### 4.5 Inbox — approve and confirm on the go (G3)

Menu → Inbox (also from Home's needs-you chip). One list, three sources (approvals, AI drafts, exceptions), newest first:

- Each item = a **decision card**: plain sentence ("AI recorded *Fuel — Rs 4,500* from your import. Look right?"), the two or three facts that matter, then two thumb buttons: **[ Confirm ] [ Not right ]** (destructive/complex resolution opens the full surface).
- Swipe right = confirm (same guarded posting path as desktop `a` key; unresolved items refuse with "needs accounts picked — open it"), swipe left = skip.
- Progress line "3 of 9 done" — the desktop match-session, translated to touch.

### 4.6 Reports that read like messages (G5)

Statements on a phone become **stacked answer cards**, not tables:

```
THIS QUARTER            [period chips row]
┌ Money made ────────────── Rs 118,000 ┐
│ mostly from Sales                    │
├ Money spent ───────────── Rs 96,100  ┤
│ biggest: Cost of goods                │
├ What's left ⓘ ═══════════ Rs 21,900  ┤   ← double rule = Ledger signature
└ [ See the full statement → ]         ┘
```

- Period = the same global `usePeriodStore` (chips row at top; set once, every card follows).
- Each card drills to the full statement page (which already renders acceptably via responsive tables + print CSS for sharing PDFs).
- Balance sheet card: "You own Rs X · You owe Rs Y · Yours: Rs Z". Cash flow: "Came in / went out / change".
- The AI narrative (CFO briefing) renders above the cards — it's already the most phone-native artifact the app has.

### 4.7 Close, payroll, and the rest

- **Close the Month** is already card-shaped — it ships on phones as-is (verified: `rule-subtotal` rows + links). Same for Command Center.
- Payroll run, PO editor, budget editor, report builder: **view + approve on phone; author on desktop.** Their pages stay reachable (SmartTable cards), and each gets a top note "Easier on a computer — we'll keep your place" rather than a crippled editor. This is an explicit scope decision: authoring surfaces that are genuinely table-shaped aren't worth forcing into steps in this pass.
- Settings: already simple cards; language/theme/module toggles work today.

---

## 5. Interaction standards (the mobile contract)

| Pattern | Rule |
|---|---|
| Sheets | Kit `Sheet`: drag handle, ≤92vh, sticky footer with THE one action, safe-area padding, backdrop tap closes, Esc/back closes |
| Sticky CTA | Every task screen has exactly one, bottom-center, ≥52px tall, above the tab bar |
| Swipe actions | Max 2 per side; always mirrored by a visible ⋯ (never gesture-only); destructive swipes need a confirm tap |
| Pull-to-refresh | Every list (kit component); invalidates that surface's queries |
| Steppers | Multi-step sheets show "Step 1 of 3" + back; state survives accidental close (draft kept) |
| Feedback | Success = toast **above the tab bar** + light haptic (`navigator.vibrate(10)` where supported); errors say what to fix in plain words |
| Type | Body ≥16px inside mobile surfaces (kit baseline), `money` figures tabular mono, one hero number per screen |
| Motion | Kit/spring tokens from `design-system/motion`; reduced-motion → fades |
| Back | Android back / iOS edge-swipe closes the top sheet first, then navigates — never loses typed input without the dirty guard |
| Offline | Capture queue persists to localStorage; lists show cached data with a quiet "updated Xm ago" line |

---

## 6. Copy (plain words, per surface)

| Surface | Visible words (accounting term as quiet hint) |
|---|---|
| Money tab | "Owed to me" (Receivables) · "I owe" (Payables) · "Activity" |
| Chase | "Remind" · "14 days late" · "They paid" |
| Capture | "Snap a receipt" · "Say it or type it" · "Review & save" |
| Inbox | "Look right?" · "Confirm" · "Not right" |
| Reports | "Money made / spent / what's left" (Income statement) · "You own / you owe / yours" (Balance sheet) |
| Invoice flow | "Who is it for?" · "What did you sell?" · "When should they pay?" |

All via `en.json` keys with `ur.json` mirrored per screen (RTL layout already scaffolded — sheets and bars must use logical properties).

---

## 7. Architecture notes (how it builds on what exists)

- **No new pipelines.** Photo lane → photo-receipt spec's ingestion → AI review queue. Sentence lane → smart-entry parser. Invoice flow → existing draft/create/submit hooks. Inbox → the three existing queues. *One accounting engine, untouched.*
- **Render-split only where a flow differs** (Capture sheet, invoice steps, Money tab, Inbox, report cards). Plain lists stay on SmartTable's built-in card collapse — the phase-2 investment means this pass builds ~6 surfaces, not 90.
- New kit members: `StepSheet` (stepper scaffold), `DecisionCard`, `SegmentedControl`, `AnswerCard` (report card), `useCaptureQueue`. All in `design-system/` under the lint ratchet.
- `MobileNav` tab change (Reports→Money) is config, not surgery; Menu regenerates from `nav.config` (kills the drift, G8).

---

## 8. Accessibility & performance

- VoiceOver/TalkBack: sheets announce as dialogs; swipe actions have button equivalents (already kit policy); decision cards read as one sentence then actions.
- Contrast: Ledger tokens are AA on both modes; hero numbers ≥ 4.5:1 verified in the catalog.
- Performance: tab surfaces lazy-load; images from the camera compress client-side before upload (existing `imageCapture.js`); capture sheet opens in <200ms (no data fetch on open); lists virtualize via SmartTable's cap.

---

## 9. Rollout (each pass shippable, in order)

| Pass | Ships | Size |
|---|---|---|
| M1 | Capture sheet (3 lanes + confirmation card + offline queue) — the heart | L |
| M2 | Money tab (segmented lists + swipe Remind/Record payment) + bottom-bar swap | M |
| M3 | Invoice/Bill 3-step sheet flow | L |
| M4 | Inbox decision cards (approve/confirm on the go) | M |
| M5 | Report answer cards + period chips | M |
| M6 | Polish: haptics, Home Explain/role-parity, Menu from nav.config, Urdu fill, a11y audit at 375px | M |

Success = the five daily jobs each measured at ≤3 taps; a first-time phone user records a sale, sends an invoice, and chases a payment without help; 121+ tests stay green; no accounting path bypassed.

---

*Next step after user review: superpowers:writing-plans for pass M1 (Capture sheet).*
