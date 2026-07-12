# Mobile-First Redesign — First Pass: Foundations + Daily Loop

**Date:** 2026-07-12
**Status:** Approved (design + Home mockup walkthrough)
**Repo:** `vousfin-frontend-main` (frontend only)

## Goal

Rebuild VousFin's phone experience as purpose-built mobile screens — clean, calm, one-handed, large touch targets, fewer taps/scrolls — instead of the desktop layout reflowing. This first pass ships the reusable mobile kit + the daily-loop screens; later passes reuse the kit everywhere.

## Decisions (locked with user)

- **First slice:** foundations + daily loop.
- **Feel:** native-app (full-height sheets, swipe actions, pull-to-refresh, thumb-zone primaries).
- **Look:** keep the active theme + `--c-*` tokens; only layout/spacing/hierarchy/touch change.
- **Method:** mobile-first render split — render a **separate mobile component** where a screen needs a real redesign; desktop is untouched. Upgrade shared surfaces (Modal) once so all screens benefit.

## Audit findings (why)

Nav shell (bottom tab bar + menu sheet) is already mobile-first and good. The problem is content: pages are desktop grids that collapse; every list is a `<table>` that auto-stacks each row into generic "label: value" lines with cramped inline action buttons; modals are centered desktop dialogs; editors don't fit; type/targets are small. `useWindowSize().isMobile` (<768) and a `.mobile-bottom-sheet` seam already exist to build on.

## Architecture

- Breakpoint: **phone = width < 768** (matches existing `Modal`/`useWindowSize`). Tablets keep desktop content but the existing bottom nav.
- Render split at the page top: `if (isMobile) return <MobileX/>`. Early return leaves the desktop component fully intact below.
- Shared upgrade: `Modal` becomes a true full-height sheet on mobile (drag handle, safe-area, scrollable body) — every modal improves at once, no API change.

## Components — the mobile kit (`src/components/mobile/`)

1. **`useIsMobile()`** (`hooks/useIsMobile.js`) — `matchMedia('(max-width: 767px)')`, SSR-safe (defaults false), reactive via listener. Returns boolean.
2. **`Sheet.jsx`** — full-height bottom sheet. Props: `{ isOpen, onClose, title, children, footer?, className }`. Portal to `document.body`; backdrop (tap to close); panel `max-h-[92vh]` with sticky header (drag handle + title + close), scrollable body, optional sticky `footer` (thumb-zone). Safe-area bottom padding. Slide-up animation; respects `prefers-reduced-motion`. Locks body scroll while open.
3. **`ListCard.jsx`** — tappable row card. Props: `{ leading?, title, subtitle?, trailing?, trailingSub?, onClick, className }`. ≥56px tall, full-width tap target, 16px padding, hairline separation. Pure presentational.
4. **`SwipeRow.jsx`** — wraps a ListCard; horizontal touch-drag reveals up to 2 action buttons (`actions: [{ label, icon, tone, onClick }]`). Touch-only (pointer/touch handlers); on non-touch it renders the card normally and exposes the same actions via a trailing "⋯" button that opens a small action `Sheet` (so actions are always reachable, never gesture-only). Defensive: threshold + snap-back; never interferes with vertical scroll (only engages past a horizontal threshold).
5. **`PullToRefresh.jsx`** — wraps scrollable content; touch pull past threshold at scrollTop 0 calls `onRefresh()` (returns a promise; shows a spinner). No-op when not touch / reduced-motion. Props: `{ onRefresh, children }`.
6. **`MobilePage.jsx`** — screen scaffold. Props: `{ title, subtitle?, right?, children, cta? }`. Large-title header (28px), generous 20px horizontal padding, safe-area top, and an optional sticky bottom `cta` (thumb-zone). Consistent vertical rhythm.
7. **Tokens/utilities** (in `index.css`): `.tap-target` (min-h/w 48px), safe-area helpers (`.pb-safe`, `.pt-safe` using `env(safe-area-inset-*)`), mobile type baseline (body 16px, labels ≥13px within mobile screens).

## Screens — daily loop (`this pass`)

### MobileHome (`src/pages/dashboard/MobileHome.jsx`)
Rendered by `Dashboard.jsx` when `isMobile`. Uses existing hooks (`useDashboardAll`, `useTransactions({limit:3})`, `useAutonomyInbox`, `useBusinessStore`). Vertical order:
1. Greeting + business name.
2. **Cash on hand** hero (one big number).
3. **"N things need you"** chip → `/command-center` (count from inbox `counts.actions` + attention items; hidden when 0).
4. **Money in / Money out** two-tile row (`kpis.revenue` / `kpis.expenses`).
5. **Recent** — last 3 transactions as `ListCard`s (in/out icon, description, date, signed amount) → tap opens the transaction (or details).
6. **See more** link → the full desktop dashboard sections are NOT shown on mobile; instead a link to `/financial-reports/income-statement` and the existing detail lives on desktop. (v1: "See more" scrolls to a lightweight collapsible with the KPI strip; keep minimal.)
7. Sticky **＋ Record something** CTA (thumb zone) → `openTxModal()`.
Wrapped in `PullToRefresh` (invalidates dashboard + transactions queries).

### Record flow
`TransactionFormModal` already opens via the global `Modal`; the `Modal` mobile upgrade makes it a full-height sheet. Simple mode is already the default. No new component; verify the sheet presentation + that Save is reachable (the form's own submit sits at the end of the scrollable body — acceptable for v1; a sticky footer is a later refinement).

### MobileTransactions (`src/pages/transactions/MobileTransactions.jsx`)
Rendered by `TransactionsList.jsx` when `isMobile`. Uses existing `useTransactions`. Header (MobilePage "Transactions") + a compact money-in/out summary + a `PullToRefresh` list of `SwipeRow`(`ListCard`) items (date · description · signed amount, color by in/out). Swipe/⋯ actions: "Details", and "Reverse" when reversible. Sticky **＋ Record** CTA. Replaces the sideways-scrolling table on phones.

## Wiring (minimal, reversible)

- `Dashboard.jsx`: add `const isMobile = useIsMobile(); if (isMobile) return <MobileHome/>` as the first line of the returned component body (before the desktop JSX).
- `TransactionsList.jsx`: same pattern → `<MobileTransactions/>`.
- `Modal.jsx`: replace the mobile branch with the full-height sheet treatment (drag handle, `max-h-[92vh]`, safe-area, sticky header). Desktop branch unchanged.

## Error handling

- All new screens reuse existing query hooks → inherit their loading/error/skeleton behavior; show simple mobile skeletons (pulse cards) while loading and a plain "Couldn't load — pull to refresh" on error.
- Gesture components fail safe: any gesture ambiguity snaps back; actions always reachable without gestures (⋯ fallback).

## Testing (Vitest)

- `useIsMobile` — matchMedia mock: returns true/false, updates on change event.
- `Sheet` — renders title + children when open, not when closed; renders `footer` when provided; calls `onClose` on backdrop click.
- `ListCard` — renders title/subtitle/trailing; `onClick` fires on click; has a min-height/tap-target class.
- `SwipeRow` — renders the card; the ⋯ fallback exposes each action; clicking an action fires its `onClick`.
- `MobileHome` — with mocked hooks: renders cash hero + "Record" CTA; renders the needs-you chip only when count > 0; renders recent ListCards.
- Build must pass; full suite stays green. Live 375px check where reachable (login-gated screens flagged — user to glance).

## Out of scope (later passes, reuse the kit)

- Converting the remaining lists (Inventory, Invoices, Bills, Receivables/Payables) to `ListCard`.
- Editor forms (invoice/bill/item) as mobile flows with sticky footers.
- Sticky-footer submit inside `TransactionFormModal`.
- Swipe-back navigation, haptics.
